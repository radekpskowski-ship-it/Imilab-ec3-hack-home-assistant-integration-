"""Minimum interval between motion alarms (setAlarmConfig interval field, minutes)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, UnitOfTime

from . import ImilabEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ImilabAlarmInterval(entry.runtime_data)])


class ImilabAlarmInterval(ImilabEntity, NumberEntity):
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 30
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarm_interval")

    @property
    def native_value(self):
        alarm = self.coordinator.data.get("alarm")
        return alarm[6] if alarm else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.set_alarm(interval=int(value))
