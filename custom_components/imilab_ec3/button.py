"""PTZ (set_motor), siren, restart, save preset, SMB test."""

from __future__ import annotations

from miio import DeviceException

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.components.persistent_notification import async_create as notify
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from . import ImilabEntity, nas_error, nas_share
from .const import EMPTY_REGION, PRESET_SLOTS

# key, icon, miio method, params
BUTTONS = [
    ("pan_left", "mdi:arrow-left-bold", "set_motor", {"operation": 1}),
    ("pan_right", "mdi:arrow-right-bold", "set_motor", {"operation": 2}),
    # operation 3/4 (tilt up/down) left out — the tested unit only pans
    ("alarm", "mdi:alarm-light", "alarm_sound", []),
    ("restart", "mdi:restart", "restart_device", []),
]


async def async_setup_entry(hass, entry, async_add_entities):
    c = entry.runtime_data
    async_add_entities([*(ImilabButton(c, *b) for b in BUTTONS), ImilabSmbTest(c), ImilabSavePreset(c)])


class ImilabButton(ImilabEntity, ButtonEntity):
    def __init__(self, coordinator, key, icon, method, params) -> None:
        super().__init__(coordinator, key)
        self._attr_icon = icon
        if key == "restart":
            self._attr_device_class = ButtonDeviceClass.RESTART
            self._attr_entity_category = EntityCategory.CONFIG
        self._method = method
        self._params = params

    async def async_press(self) -> None:
        await self.coordinator.send(self._method, self._params)


class ImilabSmbTest(ImilabEntity, ButtonEntity):
    """The camera connects to the SMB share from the options (nas_list_dir); result in a sensor + notification."""

    _attr_icon = "mdi:folder-network"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "smb_test")

    async def async_press(self) -> None:
        c = self.coordinator
        share = nas_share(c.entry.options)
        if share is None:
            result, detail = "not_configured", "Configure the SMB share in the integration options"
        else:
            try:
                dirs = await c.send("nas_list_dir", {"share": share})
                result = "ok"
                detail = ", ".join(map(str, dirs)) if dirs else "(empty directory)"
            except DeviceException as err:
                result, detail = "error", nas_error(err)
        c.smb_test = (result, detail, dt_util.now())
        target = f"\\\\{share['addr']}\\{share['dir']}" if share else "-"
        notify(self.hass, f"**{result}** — {target}\n\n{detail}", title="Imilab EC3: SMB test",
               notification_id="imilab_ec3_smb_test")
        c.async_update_listeners()


class ImilabSavePreset(ImilabEntity, ButtonEntity):
    """Save the current PTZ position into the first free slot (1–6)."""

    _attr_icon = "mdi:map-marker-plus"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "save_preset")

    async def async_press(self) -> None:
        used = {p.get("location") for p in self.coordinator.data.get("presets") or []}
        free = next((n for n in PRESET_SLOTS if n not in used), None)
        if free is None:
            raise HomeAssistantError("All 6 presets are used — delete one with imilab_ec3.delete_preset")
        await self.coordinator.send("set_favoritelocation", [{"status": "set", "location": free, "region": EMPTY_REGION}])
        await self.coordinator.async_request_refresh()
