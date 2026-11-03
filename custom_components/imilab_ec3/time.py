"""Monitoring schedule hours (setAlarmConfig, used in the "schedule" mode)."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory

from . import ImilabEntity


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([ImilabAlarmTime(c, "alarm_start", 1), ImilabAlarmTime(c, "alarm_end", 3)])


class ImilabAlarmTime(ImilabEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, key, index) -> None:
        super().__init__(coordinator, key)
        self._index = index

    @property
    def native_value(self) -> time | None:
        alarm = self.coordinator.data.get("alarm")
        if not alarm:
            return None
        try:
            return time(alarm[self._index], alarm[self._index + 1])
        except ValueError:
            return None

    async def async_set_value(self, value: time) -> None:
        prefix = "start" if self._index == 1 else "end"
        await self.coordinator.set_alarm(**{f"{prefix}_h": value.hour, f"{prefix}_m": value.minute})
