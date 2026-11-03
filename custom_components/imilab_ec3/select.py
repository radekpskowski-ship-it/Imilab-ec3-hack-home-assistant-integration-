"""Selects: night mode, SD recording, motion sensitivity, monitoring schedule, PTZ preset."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory

from . import ImilabEntity
from .const import ALARM_MODES, NIGHT_MODES, RECORD_MODES, SENSITIVITY


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([ImilabNightMode(c), ImilabRecordMode(c), ImilabSensitivity(c), ImilabAlarmMode(c), ImilabPreset(c)])


class ImilabNightMode(ImilabEntity, SelectEntity):
    _attr_options = NIGHT_MODES
    _attr_icon = "mdi:weather-night"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "night_mode")

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.data.get("night_mode")
        try:
            return NIGHT_MODES[int(value)]
        except (TypeError, ValueError, IndexError):
            return None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.send("set_night_mode", [NIGHT_MODES.index(option)])
        self.coordinator.data["night_mode"] = NIGHT_MODES.index(option)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class ImilabRecordMode(ImilabEntity, SelectEntity):
    """SD card recording (set_motion_record: off = continuous, on = on motion, stop = disabled)."""

    _attr_options = list(RECORD_MODES.values())
    _attr_icon = "mdi:record-rec"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "record_mode")

    @property
    def current_option(self) -> str | None:
        return RECORD_MODES.get(self.coordinator.data.get("motion_record"))

    async def async_select_option(self, option: str) -> None:
        value = next(k for k, v in RECORD_MODES.items() if v == option)
        await self.coordinator.send("set_motion_record", [value])
        self.coordinator.data["motion_record"] = value
        self.async_write_ha_state()


class ImilabSensitivity(ImilabEntity, SelectEntity):
    """Motion detection sensitivity — all 32 motion_region cells at once."""

    _attr_options = list(SENSITIVITY)
    _attr_icon = "mdi:tune-vertical"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "sensitivity")

    @property
    def current_option(self) -> str | None:
        region = self.coordinator.data.get("region") or []
        for name, level in SENSITIVITY.items():
            if region and all(v == level for v in region):
                return name
        return None

    @property
    def extra_state_attributes(self):
        return {"cells": self.coordinator.data.get("region")}

    async def async_select_option(self, option: str) -> None:
        region = [SENSITIVITY[option]] * 32
        await self.coordinator.send("set_motion_region", region)
        self.coordinator.data["region"] = region
        self.async_write_ha_state()


class ImilabAlarmMode(ImilabEntity, SelectEntity):
    """Monitoring (Mi Home motion alarms): off / all day / schedule (hours in the time entities)."""

    _attr_options = list(ALARM_MODES.values())
    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarm_mode")

    @property
    def current_option(self) -> str | None:
        alarm = self.coordinator.data.get("alarm")
        return ALARM_MODES.get(alarm[0]) if alarm else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.set_alarm(mode=next(k for k, v in ALARM_MODES.items() if v == option))


class ImilabPreset(ImilabEntity, SelectEntity):
    """Go to a saved PTZ preset. Save/delete: button or the imilab_ec3.*_preset services."""

    _attr_icon = "mdi:camera-marker"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "preset")
        self._attr_current_option = None

    @property
    def options(self) -> list[str]:
        presets = self.coordinator.data.get("presets") or []
        return [str(p["location"]) for p in sorted(presets, key=lambda p: p["location"])] or ["none"]

    async def async_select_option(self, option: str) -> None:
        if option == "none":
            return
        await self.coordinator.send("set_favoritelocation", [{"status": "ctrl", "location": int(option)}])
        self._attr_current_option = option
        self.async_write_ha_state()
