"""Sensors: Wi-Fi, uptime, NAS, camera system status (SSH ha_cmd.sh status), day/night, presets."""

from __future__ import annotations

import socket
import struct

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory, UnitOfInformation, UnitOfTime,
)
from homeassistant.util import dt as dt_util

from . import ImilabEntity
from .const import NAS_ERRORS, NAS_STATES


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([
        ImilabRssi(c), ImilabUptime(c), ImilabNasStatus(c), ImilabSmbTestResult(c), ImilabPresets(c),
        *(ImilabStatusSensor(c, *d) for d in STATUS_SENSORS),
    ])


def _sd(key):
    def get(st):
        sd = st.get("sd") or {}
        if not sd.get("mounted"):
            return None
        if key == "used_pct":
            return round(sd["used_kb"] * 100 / sd["total_kb"], 1) if sd.get("total_kb") else None
        return round(sd[key] / 1024 / 1024, 2)
    return get


def _mem_used(st):
    if not st.get("mem_total_kb"):
        return None
    return round((st["mem_total_kb"] - st["mem_avail_kb"]) * 100 / st["mem_total_kb"], 1)


DIAG, MEAS = EntityCategory.DIAGNOSTIC, SensorStateClass.MEASUREMENT
# (key, getter(status), unit, device_class, state_class, category, icon)
STATUS_SENSORS = [
    ("cpu", lambda st: st.get("cpu"), PERCENTAGE, None, MEAS, DIAG, "mdi:cpu-32-bit"),
    ("mem_used", _mem_used, PERCENTAGE, None, MEAS, DIAG, "mdi:memory"),
    ("mem_free", lambda st: round(st["mem_avail_kb"] / 1024, 1) if st.get("mem_avail_kb") else None,
     UnitOfInformation.MEBIBYTES, SensorDeviceClass.DATA_SIZE, MEAS, DIAG, "mdi:memory"),
    ("load", lambda st: st.get("load"), None, None, MEAS, DIAG, "mdi:gauge"),
    ("sd_free", _sd("free_kb"), UnitOfInformation.GIBIBYTES, SensorDeviceClass.DATA_SIZE, MEAS, None, "mdi:sd"),
    ("sd_total", _sd("total_kb"), UnitOfInformation.GIBIBYTES, SensorDeviceClass.DATA_SIZE, None, DIAG, "mdi:sd"),
    ("sd_used", _sd("used_pct"), PERCENTAGE, None, MEAS, None, "mdi:sd"),
    ("sd_state", lambda st: "mounted" if (st.get("sd") or {}).get("mounted") else "missing",
     None, SensorDeviceClass.ENUM, None, DIAG, "mdi:sd"),
    ("wifi_quality", lambda st: st.get("wifi_quality"), PERCENTAGE, None, MEAS, DIAG, "mdi:wifi"),
    ("daynight", lambda st: st.get("daynight") or None, None, SensorDeviceClass.ENUM, None, None, "mdi:theme-light-dark"),
    # EV from the miio_algo log; day and night use different scales, so treat it as relative
    ("ev", lambda st: st.get("ev"), None, None, MEAS, None, "mdi:brightness-6"),
]
ENUM_OPTIONS = {"sd_state": ["mounted", "missing"], "daynight": ["day", "night"]}


class ImilabStatusSensor(ImilabEntity, SensorEntity):
    """Value from the `status` JSON (SSH, hack/bin/ha_cmd.sh)."""

    def __init__(self, coordinator, key, getter, unit, device_class, state_class, category, icon) -> None:
        super().__init__(coordinator, key)
        self._getter = getter
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = category
        self._attr_icon = icon
        if key in ENUM_OPTIONS:
            self._attr_options = ENUM_OPTIONS[key]

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.get("status"))

    @property
    def native_value(self):
        try:
            return self._getter(self.coordinator.data["status"])
        except (KeyError, TypeError, ZeroDivisionError):
            return None


class ImilabPresets(ImilabEntity, SensorEntity):
    _attr_icon = "mdi:camera-marker"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "presets")

    @property
    def native_value(self):
        presets = self.coordinator.data.get("presets")
        return len(presets) if isinstance(presets, list) else None

    @property
    def extra_state_attributes(self):
        presets = self.coordinator.data.get("presets") or []
        return {
            "saved": sorted(p.get("location") for p in presets),
            "saved_at": {p.get("location"): dt_util.utc_from_timestamp(p["timet"]).isoformat() for p in presets if p.get("timet")},
        }


class ImilabRssi(ImilabEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "rssi")

    @property
    def native_value(self):
        return self.coordinator.data.get("rssi")


class ImilabUptime(ImilabEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_suggested_unit_of_measurement = UnitOfTime.HOURS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "uptime")

    @property
    def native_value(self):
        return self.coordinator.data.get("uptime")


def _ip(addr) -> str | None:
    """nas_get_config returns the server address as a little-endian int."""
    if isinstance(addr, int):
        return socket.inet_ntoa(struct.pack("<I", addr))
    return addr


class ImilabNasStatus(ImilabEntity, SensorEntity):
    _attr_icon = "mdi:nas"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [*NAS_STATES.values(), "error"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "nas_status")

    @property
    def native_value(self):
        nas = self.coordinator.data.get("nas")
        if not nas:
            return None
        if nas.get("error_code"):
            return "error"
        return NAS_STATES.get(nas.get("state"))

    @property
    def extra_state_attributes(self):
        nas = self.coordinator.data.get("nas") or {}
        share = nas.get("share") or {}
        last = nas.get("last_sync_time")
        code = nas.get("error_code")
        return {
            "error": NAS_ERRORS.get(code, code) if code else None,
            "last_sync": dt_util.utc_from_timestamp(last).isoformat() if last else None,
            "sync_interval_s": nas.get("sync_interval"),
            "retention_s": nas.get("video_retention_time"),
            "server": _ip(share.get("addr")),
            "share": share.get("dir"),
        }


class ImilabSmbTestResult(ImilabEntity, SensorEntity):
    _attr_icon = "mdi:folder-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["not_tested", "ok", "error", "not_configured"]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "smb_test_result")

    @property
    def native_value(self):
        return self.coordinator.smb_test[0]

    @property
    def extra_state_attributes(self):
        _, detail, when = self.coordinator.smb_test
        return {"detail": detail, "tested_at": when.isoformat() if when else None}
