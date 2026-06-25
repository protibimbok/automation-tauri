from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class BusMessage:
    kind: str
    id: str
    route: str
    payload: Any

    @classmethod
    def event(cls, route: str, payload: Any) -> BusMessage:
        return cls(kind="event", id="", route=route, payload=payload)

    @classmethod
    def request(cls, id: str, route: str, payload: Any) -> BusMessage:
        return cls(kind="request", id=id, route=route, payload=payload)

    def to_response(self, payload: Any) -> BusMessage:
        return BusMessage(
            kind="response",
            id=self.id,
            route=self.route,
            payload=payload,
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "kind": self.kind,
                "id": self.id,
                "route": self.route,
                "payload": self.payload,
            }
        )

    @classmethod
    def from_json(cls, line: str) -> BusMessage:
        data = json.loads(line)
        return cls(
            kind=data["kind"],
            id=data.get("id", ""),
            route=data["route"],
            payload=data.get("payload"),
        )
