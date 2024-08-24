import dataclasses
import time
from dataclasses import dataclass, field
from typing import Optional

from gwproactor.config.proactor_settings import MQTT_LINK_POLL_SECONDS

import_time = time.time()


@dataclass
class LinkMessageTimes:
    last_send: float = field(default_factory=time.time)
    last_recv: float = field(default_factory=time.time)

    def next_ping_second(self, link_poll_seconds: float) -> float:
        return self.last_send + link_poll_seconds

    def seconds_until_next_ping(self, link_poll_seconds: float) -> float:
        return self.next_ping_second(link_poll_seconds) - time.time()

    def time_to_send_ping(self, link_poll_seconds: float) -> bool:
        return time.time() > self.next_ping_second(link_poll_seconds)

    def get_str(
        self,
        *,
        link_poll_seconds: float = MQTT_LINK_POLL_SECONDS,
        relative: bool = True,
    ) -> str:
        adjust = import_time if relative else 0
        return (
            f"n:{time.time() - adjust:5.2f}  lps:{link_poll_seconds:5.2f}  "
            f"ls:{self.last_send - adjust:5.2f}  lr:{self.last_recv - adjust:5.2f}  "
            f"nps:{self.next_ping_second(link_poll_seconds) - adjust:5.2f}  "
            f"snp:{self.next_ping_second(link_poll_seconds):5.2f}  "
            f"tsp:{int(self.time_to_send_ping(link_poll_seconds))}"
        )

    def __str__(self) -> str:
        return self.get_str()


class MessageTimes:
    _links: dict[str, LinkMessageTimes]

    def __init__(self) -> None:
        self._links = {}

    def add_link(self, name: str) -> None:
        self._links[name] = LinkMessageTimes()

    def get_copy(self, link_name: str) -> LinkMessageTimes:
        return dataclasses.replace(self._links[link_name])

    def update_send(self, link_name: str, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        self._links[link_name].last_send = now

    def update_recv(self, link_name: str, now: Optional[float] = None) -> None:
        if now is None:
            now = time.time()
        self._links[link_name].last_recv = now

    def link_names(self) -> list[str]:
        return list(self._links.keys())
