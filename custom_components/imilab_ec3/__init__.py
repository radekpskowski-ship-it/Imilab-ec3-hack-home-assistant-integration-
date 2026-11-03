"""Imilab EC3 (chuangmi.camera.025b02) — local miio control + live view through go2rtc."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from datetime import timedelta
from urllib.parse import urlsplit

import voluptuous as vol
from miio import Device, DeviceError, DeviceException

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_SMB_ADDR, CONF_SMB_DIR, CONF_SMB_GROUP, CONF_SMB_NAME, CONF_SMB_PASS, CONF_SMB_USER,
    CONF_SNAPSHOT_PASSWORD, CONF_SNAPSHOT_URL, CONF_SNAPSHOT_USER, CONF_STREAM_URL, CONF_TOKEN,
    DOMAIN, EMPTY_REGION, NAS_ERRORS, PLATFORMS, PRESET_SLOTS, PROPS, SCAN_INTERVAL_S, SSH_KEY, TOKEN_FILE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_TOKEN): cv.string,
                vol.Optional(CONF_STREAM_URL): cv.string,
                vol.Optional(CONF_SNAPSHOT_URL): cv.string,
                vol.Optional(CONF_SNAPSHOT_USER): cv.string,
                vol.Optional(CONF_SNAPSHOT_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=dict(config[DOMAIN]))
        )
    return True


def ssh_cmd(host: str, command: str) -> str | None:
    """Run a command on the camera over dropbear; the key is forced to hack/bin/ha_cmd.sh."""
    if not os.path.exists(SSH_KEY):
        return None
    try:
        return subprocess.run(
            ["ssh", "-i", SSH_KEY, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=10", "-o", "LogLevel=ERROR",
             f"root@{host}", command],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, OSError) as err:
        _LOGGER.warning("SSH %s on %s failed: %s", command, host, err)
        return None


def fetch_status(host: str) -> dict | None:
    out = ssh_cmd(host, "status")
    try:
        return json.loads(out) if out else None
    except ValueError:
        return None


def fetch_token(host: str) -> str | None:
    """Fetch the current miio token (it changes on every camera boot)."""
    out = ssh_cmd(host, "token")
    if not out or not re.fullmatch(r"[0-9a-f]{32}", out):
        return None
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(out + "\n")
    return out


class ImilabCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=SCAN_INTERVAL_S))
        self.entry = entry
        self.device = Device(entry.data[CONF_HOST], entry.data[CONF_TOKEN], timeout=5)
        self._lock = asyncio.Lock()
        self.info: dict = {}
        self.smb_test: tuple = ("not_tested", None, None)

    async def _refresh_token(self) -> bool:
        host = self.entry.data[CONF_HOST]
        token = await self.hass.async_add_executor_job(fetch_token, host)
        if not token or token == self.device.token.hex():
            return False
        _LOGGER.info("Camera %s has a new miio token — updating", host)
        self.device = Device(host, token, timeout=5)
        self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, CONF_TOKEN: token})
        return True

    async def send(self, method: str, params=None):
        # python-miio is not thread-safe — one command at a time
        params = params if params is not None else []
        async with self._lock:
            try:
                return await self.hass.async_add_executor_job(self.device.send, method, params)
            except DeviceError:
                # the camera answered with an error — the token is fine
                raise
            except DeviceException:
                # no answer = usually a wrong signature after a camera reboot
                if not await self._refresh_token():
                    raise
                return await self.hass.async_add_executor_job(self.device.send, method, params)

    async def _async_update_data(self) -> dict:
        try:
            values = await self.send("get_prop", PROPS)
            self.info = await self.send("miIO.info", [])
        except DeviceException as err:
            raise UpdateFailed(f"miio: {err}") from err
        data = dict(zip(PROPS, values))
        old = self.data or {}
        data["alarm"] = _json_list(data.get("motion_alarm"))
        data["region"] = _json_list(data.get("motion_region"))
        # extra reads — one failing must not break the rest
        for key, method, params in (
            ("nas", "nas_get_config", {}),
            ("presets", "get_favoritelocation", []),
            ("focus", "get_focus_area_info", []),
        ):
            try:
                data[key] = await self.send(method, params)
            except DeviceException:
                data[key] = old.get(key)
        if isinstance(data.get("focus"), list):
            data["focus"] = data["focus"][0] if data["focus"] else {}
        data["status"] = await self.hass.async_add_executor_job(fetch_status, self.entry.data[CONF_HOST])
        data["rssi"] = int(self.info.get("ap", {}).get("rssi", 0))
        data["uptime"] = self.info.get("life")
        return data

    async def set_alarm(self, **changes) -> None:
        """Change fields of setAlarmConfig, keeping the others."""
        names = ["mode", "start_h", "start_m", "end_h", "end_m", "notify", "interval"]
        cfg = list(self.data.get("alarm") or [0, 0, 0, 23, 59, 0, 5])
        for k, v in changes.items():
            cfg[names.index(k)] = int(v)
        await self.send("setAlarmConfig", cfg)
        self.data["alarm"] = cfg
        self.async_update_listeners()


def _json_list(value) -> list | None:
    try:
        v = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return None
    return v if isinstance(v, list) else None


class ImilabEntity(CoordinatorEntity[ImilabCoordinator]):
    """Base entity. Names come from translations (translation_key = key); key None = device name."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ImilabCoordinator, key: str | None) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._key = key
        if key is None:
            self._attr_name = None
            key = "camera"
        else:
            self._attr_translation_key = key
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        info = coordinator.info
        snapshot = urlsplit(entry.data.get(CONF_SNAPSHOT_URL) or "")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, info["mac"].lower())} if info.get("mac") else set(),
            name="Imilab EC3",
            manufacturer="Imilab / Chuangmi",
            model="EC3 (chuangmi.camera.025b02)",
            sw_version=info.get("fw_ver"),
            hw_version=info.get("hw_ver"),
            configuration_url=f"{snapshot.scheme}://{snapshot.netloc}" if snapshot.netloc else None,
        )


def nas_share(options: dict) -> dict | None:
    """Share object for miio_nas — every key is required by libmiio_samba."""
    if not options.get(CONF_SMB_ADDR):
        return None
    return {
        "type": 1,
        "name": options.get(CONF_SMB_NAME) or "NAS",
        "addr": options[CONF_SMB_ADDR],
        "dir": (options.get(CONF_SMB_DIR) or "").strip("\\/").replace("/", "\\"),
        "group": options.get(CONF_SMB_GROUP) or "WORKGROUP",
        "user": options.get(CONF_SMB_USER) or "",
        "pass": options.get(CONF_SMB_PASS) or "",
    }


def nas_error(err: Exception) -> str:
    code = err.args[0].get("code") if err.args and isinstance(err.args[0], dict) else None
    return NAS_ERRORS.get(code, f"error {code if code is not None else err}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = ImilabCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    _register_services(hass)
    return True


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "save_preset"):
        return
    schema = vol.Schema({vol.Required("location"): vol.All(vol.Coerce(int), vol.Range(1, max(PRESET_SLOTS)))})

    def _coordinator() -> ImilabCoordinator:
        entries = [e for e in hass.config_entries.async_entries(DOMAIN) if getattr(e, "runtime_data", None)]
        if not entries:
            raise HomeAssistantError("Imilab EC3 is not loaded")
        return entries[0].runtime_data

    async def _preset(call: ServiceCall, status: str) -> None:
        c = _coordinator()
        params = {"status": status, "location": call.data["location"]}
        if status == "set":
            params["region"] = EMPTY_REGION
        try:
            await c.send("set_favoritelocation", [params])
        except DeviceException as err:
            raise HomeAssistantError(f"PTZ preset: {err}") from err
        await c.async_request_refresh()

    async def save(call: ServiceCall) -> None:
        await _preset(call, "set")

    async def goto(call: ServiceCall) -> None:
        await _preset(call, "ctrl")

    async def delete(call: ServiceCall) -> None:
        await _preset(call, "del")

    hass.services.async_register(DOMAIN, "save_preset", save, schema=schema)
    hass.services.async_register(DOMAIN, "goto_preset", goto, schema=schema)
    hass.services.async_register(DOMAIN, "delete_preset", delete, schema=schema)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await entry.runtime_data.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
