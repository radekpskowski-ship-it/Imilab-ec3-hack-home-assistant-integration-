"""On/off switches (get_prop / set_<prop>), NAS, push, siren on motion, motion tracking."""

from __future__ import annotations

from miio import DeviceException

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_HOST, EntityCategory
from homeassistant.exceptions import HomeAssistantError

from . import ImilabEntity, nas_error, nas_share, ssh_cmd
from .const import CONF_SMB_INTERVAL, CONF_SMB_RETENTION, NAS_STATE_OFF, NAS_STATE_ON

# (key = get_prop name, set_<key> command), icon, category
SWITCHES = [
    ("power", "mdi:cctv", None),
    ("light", "mdi:led-on", EntityCategory.CONFIG),
    ("wdr", "mdi:hdr", EntityCategory.CONFIG),
    ("full_color", "mdi:palette", EntityCategory.CONFIG),
    ("watermark", "mdi:clock-outline", EntityCategory.CONFIG),
    ("flip", "mdi:flip-vertical", EntityCategory.CONFIG),
    # enables the miio_algo detector — also needed for the HA motion sensor (with monitoring != off)
    ("motion_detection_enable", "mdi:motion-sensor", EntityCategory.CONFIG),
    ("improve_program", "mdi:cloud-upload", EntityCategory.CONFIG),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([
        *(ImilabSwitch(c, *s) for s in SWITCHES),
        ImilabNasSwitch(c), ImilabPushSwitch(c), ImilabSirenOnMotion(c), ImilabTrackSwitch(c),
    ])


class ImilabSwitch(ImilabEntity, SwitchEntity):
    def __init__(self, coordinator, key, icon, category) -> None:
        super().__init__(coordinator, key)
        self._attr_icon = icon
        self._attr_entity_category = category

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get(self._key)
        return None if value is None else value == "on"

    async def _set(self, value: str) -> None:
        await self.coordinator.send(f"set_{self._key}", [value])
        self.coordinator.data[self._key] = value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._set("off")


class ImilabNasSwitch(ImilabEntity, SwitchEntity):
    """Record to an SMB share (miio_nas). The share is configured in the integration options."""

    _attr_icon = "mdi:nas"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "nas")

    @property
    def is_on(self) -> bool | None:
        nas = self.coordinator.data.get("nas") or {}
        return nas.get("state") == NAS_STATE_ON

    async def _set(self, state: int) -> None:
        opts = self.coordinator.entry.options
        share = nas_share(opts)
        if state == NAS_STATE_ON and share is None:
            raise HomeAssistantError("Configure the SMB share in the Imilab EC3 integration options first")
        params = {"state": state}
        if share:
            params.update(
                share=share,
                sync_interval=int(opts.get(CONF_SMB_INTERVAL, "300")),
                video_retention_time=int(opts.get(CONF_SMB_RETENTION, "2592000")),
            )
        try:
            await self.coordinator.send("nas_set_config", params)
        except DeviceException as err:
            raise HomeAssistantError(f"NAS: {nas_error(err)}") from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(NAS_STATE_ON)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(NAS_STATE_OFF)


class ImilabPushSwitch(ImilabEntity, SwitchEntity):
    """Mi Home motion push notifications (notify field of setAlarmConfig)."""

    _attr_icon = "mdi:cellphone-message"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "alarm_notify")

    @property
    def is_on(self) -> bool | None:
        alarm = self.coordinator.data.get("alarm")
        return bool(alarm[5]) if alarm else None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.set_alarm(notify=1)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.set_alarm(notify=0)


class ImilabSirenOnMotion(ImilabEntity, SwitchEntity):
    """Siren on motion in the focus area (focus_area_alarm).
    The parameter MUST be a list with one object — a bare object crashes miio_devicekit."""

    _attr_icon = "mdi:alarm-light"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "focus_area_alarm")

    @property
    def is_on(self) -> bool | None:
        focus = self.coordinator.data.get("focus")
        return focus.get("focus_area_alarm") == "on" if focus else None

    async def _set(self, value: str) -> None:
        focus = dict(self.coordinator.data.get("focus") or {"focus_area": "off"})
        focus["focus_area_alarm"] = value
        await self.coordinator.send("set_focus_area_info", [focus])
        self.coordinator.data["focus"] = focus
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._set("off")


class ImilabTrackSwitch(ImilabEntity, SwitchEntity):
    """Motion tracking — the built-in miio_algo tracker pans the camera (own detector, works with
    Mi Home motion detection off). Over SSH: ha_cmd.sh track on|off. Volatile — off after a camera reboot."""

    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "track")

    @property
    def is_on(self) -> bool | None:
        status = self.coordinator.data.get("status")
        return status.get("track") if status else None

    async def _set(self, value: str) -> None:
        host = self.coordinator.entry.data[CONF_HOST]
        out = await self.hass.async_add_executor_job(ssh_cmd, host, f"track {value}")
        if out != value:
            raise HomeAssistantError(f"Could not switch motion tracking (answer: {out!r})")
        if self.coordinator.data.get("status"):
            self.coordinator.data["status"]["track"] = value == "on"
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set("on")

    async def async_turn_off(self, **kwargs) -> None:
        await self._set("off")
