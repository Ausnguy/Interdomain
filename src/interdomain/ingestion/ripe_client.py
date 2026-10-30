import json
from collections.abc import Iterator
import websocket
from interdomain.config import RIPE_WS_URL


class RipeRisClient:
    def __init__(
        self,
        url: str = RIPE_WS_URL,
        connect_timeout: float = 10.0,
        idle_timeout: float = 30.0,
    ):
        self.url = url
        # RIS Live sends thousands of messages a second, so 30s of silence
        # means a dead connection, not a quiet one.
        self.connect_timeout = connect_timeout
        self.idle_timeout = idle_timeout
        self.ws: websocket.WebSocket | None = None

    def connect(self) -> None:
        self.ws = websocket.WebSocket()
        self.ws.connect(self.url, timeout=self.connect_timeout)
        self.ws.settimeout(self.idle_timeout)
        self.ws.send(json.dumps({"type": "ris_subscribe", "data": {"type": "UPDATE"}}))

    def messages(self) -> Iterator[dict]:
        if self.ws is None:
            raise RuntimeError("Client is not connected.")
        for raw_message in self.ws:
            message = json.loads(raw_message)
            kind = message.get("type")
            if kind == "ris_message":
                yield message["data"]
            elif kind == "ris_error":
                print(f"RIS Live error: {message.get('data')}")

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
            self.ws = None
