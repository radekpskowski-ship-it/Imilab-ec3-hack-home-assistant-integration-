"""Config flow for Imilab EC3 (UI + YAML import) and the SMB options flow."""

from __future__ import annotations

import os

import voluptuous as vol
from miio import Device, DeviceException

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    TextSelector, TextSelectorConfig, TextSelectorType,
)
from homeassistant.const import CONF_HOST

from .const import (
    CONF_SNAPSHOT_PASSWORD, CONF_SNAPSHOT_URL, CONF_SNAPSHOT_USER, CONF_STREAM_URL, CONF_TOKEN,
    DEFAULT_HOST, DEFAULT_SNAPSHOT_URL, DEFAULT_STREAM_URL, DOMAIN, TOKEN_FILE,
    CONF_SMB_ADDR, CONF_SMB_DIR, CONF_SMB_ENABLE, CONF_SMB_GROUP, CONF_SMB_INTERVAL, CONF_SMB_NAME,
    CONF_SMB_PASS, CONF_SMB_RETENTION, CONF_SMB_USER, NAS_INTERVALS, NAS_RETENTIONS, NAS_STATE_OFF, NAS_STATE_ON,
)
from . import fetch_token, nas_error, nas_share


def _read_token_file() -> str:
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    return ""


class ImilabConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ImilabOptionsFlow()

    async def _create(self, data: dict) -> ConfigFlowResult:
        data = dict(data)
        if not data.get(CONF_TOKEN):
            data[CONF_TOKEN] = await self.hass.async_add_executor_job(fetch_token, data[CONF_HOST]) or \
                await self.hass.async_add_executor_job(_read_token_file)
        data.setdefault(CONF_STREAM_URL, DEFAULT_STREAM_URL)
        data.setdefault(CONF_SNAPSHOT_URL, DEFAULT_SNAPSHOT_URL)
        dev = Device(data[CONF_HOST], data[CONF_TOKEN], timeout=5)
        try:
            info = await self.hass.async_add_executor_job(dev.send, "miIO.info", [])
        except DeviceException:
            return self.async_abort(reason="cannot_connect")
        await self.async_set_unique_id(info.get("mac", data[CONF_HOST]).lower().replace(":", ""))
        self._abort_if_unique_id_configured(updates=data)
        return self.async_create_entry(title="Imilab EC3", data=data)

    async def async_step_import(self, import_data: dict) -> ConfigFlowResult:
        return await self._create(import_data)

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._create(user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                    vol.Optional(CONF_TOKEN, default=""): str,
                    vol.Optional(CONF_STREAM_URL, default=DEFAULT_STREAM_URL): str,
                    vol.Optional(CONF_SNAPSHOT_URL, default=DEFAULT_SNAPSHOT_URL): str,
                    vol.Optional(CONF_SNAPSHOT_USER, default=""): str,
                    vol.Optional(CONF_SNAPSHOT_PASSWORD, default=""): str,
                }
            ),
        )


class ImilabOptionsFlow(OptionsFlow):
    """NAS (SMB) recording settings. The camera tests the share (nas_list_dir) before saving."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": "", "dirs": ""}
        opts = {**self.config_entry.options, **(user_input or {})}
        if user_input is not None:
            coordinator = self.config_entry.runtime_data
            share = nas_share(opts)
            if share is None:
                errors["base"] = "smb_no_server"
            else:
                try:
                    await coordinator.send("nas_list_dir", {"share": share})
                    await coordinator.send(
                        "nas_set_config",
                        {
                            "share": share,
                            "state": NAS_STATE_ON if opts.get(CONF_SMB_ENABLE) else NAS_STATE_OFF,
                            "sync_interval": int(opts.get(CONF_SMB_INTERVAL, "300")),
                            "video_retention_time": int(opts.get(CONF_SMB_RETENTION, "2592000")),
                        },
                    )
                except DeviceException as err:
                    errors["base"] = "smb_failed"
                    placeholders["error"] = nas_error(err)
                else:
                    return self.async_create_entry(data=opts)

        def sel(options: list[str], key: str) -> SelectSelector:
            return SelectSelector(SelectSelectorConfig(
                options=options, translation_key=key, mode=SelectSelectorMode.DROPDOWN,
            ))

        schema = vol.Schema(
            {
                vol.Required(CONF_SMB_ADDR, default=opts.get(CONF_SMB_ADDR, "")): str,
                vol.Optional(CONF_SMB_NAME, default=opts.get(CONF_SMB_NAME, "NAS")): str,
                vol.Required(CONF_SMB_DIR, default=opts.get(CONF_SMB_DIR, "")): str,
                vol.Optional(CONF_SMB_GROUP, default=opts.get(CONF_SMB_GROUP, "WORKGROUP")): str,
                vol.Optional(CONF_SMB_USER, default=opts.get(CONF_SMB_USER, "")): str,
                vol.Optional(CONF_SMB_PASS, default=opts.get(CONF_SMB_PASS, "")): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_SMB_INTERVAL, default=opts.get(CONF_SMB_INTERVAL, "300")): sel(NAS_INTERVALS, "sync_interval"),
                vol.Required(CONF_SMB_RETENTION, default=opts.get(CONF_SMB_RETENTION, "2592000")): sel(NAS_RETENTIONS, "retention"),
                vol.Required(CONF_SMB_ENABLE, default=opts.get(CONF_SMB_ENABLE, True)): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors, description_placeholders=placeholders)
