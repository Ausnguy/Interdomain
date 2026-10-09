import json
from collections.abc import Iterator
import websocket
from interdomain.config import RIPE_WS_URL


class RipeRisClient:
    def __init__(self, url: str = RIPE_WS_URL):
        self.url = url
        self.ws: websocket.WebSocket | None = None

    def connect(self) -> None:
        self.ws = websocket.WebSocket()
        self.ws.connect(self.url)
        self.ws.send(json.dumps({"type": "ris_subscribe", "data": {"type": "UPDATE"}}))

    def messages(self) -> Iterator[dict]:
        if self.ws is None:
            raise RuntimeError("Client is not connected.")
        for raw_message in self.ws:
            message = json.loads(raw_message)
            if message.get("type") == "ris_message":
                yield message["data"]

    def close(self) -> None:
        if self.ws is not None:
            self.ws.close()
            self.ws = None
