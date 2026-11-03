"""Motion (MQTT from md2mqtt.sh on the camera), connectivity, stream server."""

from __future__ import annotations

from homeassistant.components import mqtt
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from . import ImilabEntity
from .const import MOTION_OFF_DELAY_S, MOTION_TOPIC


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([ImilabMotion(c), ImilabConnected(c), ImilabRtspServer(c)])


class ImilabMotion(ImilabEntity, BinarySensorEntity):
    """On for MOTION_OFF_DELAY_S after the last /run/md_event message.
    The camera only emits events when "motion detection" is on AND "monitoring" is not off
    (push notifications may stay disabled)."""

    _attr_device_class = BinarySensorDeviceClass.MOTION

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "motion")
        self._attr_is_on = False
        self._cancel_off = None
        self._last = None

    @property
    def available(self) -> bool:
        return True

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        alarm = data.get("alarm") or [0]
        return {
            "last_motion": self._last.isoformat() if self._last else None,
            "detector_active": data.get("motion_detection_enable") == "on" and alarm[0] != 0,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if not await mqtt.async_wait_for_mqtt_client(self.hass):
            return
        self.async_on_remove(await mqtt.async_subscribe(self.hass, MOTION_TOPIC, self._message))
        self.async_on_remove(self._cancel)

    @callback
    def _cancel(self) -> None:
        if self._cancel_off:
            self._cancel_off()
            self._cancel_off = None

    @callback
    def _message(self, msg) -> None:
        self._last = dt_util.now()
        self._attr_is_on = True
        self._cancel()
        self._cancel_off = async_call_later(self.hass, MOTION_OFF_DELAY_S, self._off)
        self.async_write_ha_state()

    @callback
    def _off(self, _now) -> None:
        self._cancel_off = None
        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        # state comes from MQTT only; refresh the "detector_active" attribute
        self.async_write_ha_state()


class ImilabConnected(ImilabEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "connected")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


class ImilabRtspServer(ImilabEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "shbf2tcp")

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get("status")
        return status.get("shbf2tcp") if status else None
