"""Use the WebSocket endpoint returned by Alarm.com instead of a hard-coded host.

pyalarmdotcomajax 0.5.x hard-codes ``wss://webskt.alarm.com:8443``, which no
longer accepts connections. Alarm.com returns the current endpoint alongside the
WebSocket token (``metadata.endpoint``), so this module patches the library's
token request to read that value and point the client at it. Newer versions of
the library do the same thing natively.
"""

from __future__ import annotations

import logging

from pyalarmdotcomajax import const as c
from pyalarmdotcomajax.exceptions import UnexpectedResponse
from pyalarmdotcomajax.websockets.client import WebSocketClient

LOGGER = logging.getLogger(__name__)

_PATCHED_FLAG = "_alarmdotcom_endpoint_patch"


async def _async_get_websocket_token(self: WebSocketClient) -> str:
    """Get the WebSocket token and, when provided, the endpoint to use with it."""

    async with self._websession.get(
        url=self.WEBSOCKET_TOKEN_REQUEST_TEMPLATE.format(c.URL_BASE, ""),
        headers=self._ajax_headers,
    ) as resp:
        json_rsp = await resp.json()

    if (
        ((errors := json_rsp.get("errors")) and len(errors) > 0)
        or ((validation_errors := json_rsp.get("validation_errors")) and len(validation_errors) > 0)
        or ((processing_errors := json_rsp.get("processingErrors")) and len(processing_errors) > 0)
        or ((token_value := json_rsp.get("value")) in [None, ""])
    ):
        LOGGER.debug("Received errors while requesting WebSocket authentication token. Response: %s", json_rsp)
        raise UnexpectedResponse("Received errors while requesting WebSocket authentication token.")

    endpoint = (json_rsp.get("metadata") or {}).get("endpoint")

    if isinstance(endpoint, str) and endpoint.startswith(("wss://", "ws://")):
        # Instance attribute shadows the class-level default used by async_connect().
        self.WEBSOCKET_ENDPOINT_TEMPLATE = f"{endpoint.rstrip('/')}/?f=1&auth={{}}"
        LOGGER.debug("Using WebSocket endpoint supplied by Alarm.com: %s", endpoint)
    else:
        LOGGER.debug("Alarm.com did not supply a WebSocket endpoint; using library default.")

    return str(token_value)


def apply() -> None:
    """Install the patch once."""

    if getattr(WebSocketClient, _PATCHED_FLAG, False):
        return

    WebSocketClient._async_get_websocket_token = _async_get_websocket_token  # type: ignore[method-assign]
    setattr(WebSocketClient, _PATCHED_FLAG, True)
