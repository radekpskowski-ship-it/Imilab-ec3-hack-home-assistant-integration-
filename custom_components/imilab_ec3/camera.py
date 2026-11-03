"""Camera entity: RTSP from go2rtc (fed by shbf2tcp on the camera), snapshot from the go2rtc API."""

from __future__ import annotations

import aiohttp

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import ImilabEntity
from .const import CONF_SNAPSHOT_PASSWORD, CONF_SNAPSHOT_URL, CONF_SNAPSHOT_USER, CONF_STREAM_URL


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([ImilabCamera(entry.runtime_data)])


class ImilabCamera(ImilabEntity, Camera):
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Imilab"
    _attr_model = "EC3"

    def __init__(self, coordinator) -> None:
        ImilabEntity.__init__(self, coordinator, None)
        Camera.__init__(self)
        data = coordinator.entry.data
        self._stream_url = data[CONF_STREAM_URL]
        self._snapshot_url = data.get(CONF_SNAPSHOT_URL)
        user = data.get(CONF_SNAPSHOT_USER)
        self._auth = aiohttp.BasicAuth(user, data.get(CONF_SNAPSHOT_PASSWORD, "")) if user else None

    @property
    def is_on(self) -> bool:
        return (self.coordinator.data or {}).get("power") == "on"

    async def stream_source(self) -> str | None:
        return self._stream_url

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        if not self._snapshot_url:
            return None
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(self._snapshot_url, auth=self._auth, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                return await resp.read()
        except (aiohttp.ClientError, TimeoutError):
            return None
