from typing import Literal

from gwproto import Message
from pydantic import BaseModel


class RelayInfo(BaseModel):
    relay_name: str = ""
    closed: bool = False


class SetRelay(RelayInfo):
    TypeName: Literal["gridworks.dummy.set.relay"] = "gridworks.dummy.set.relay"


class ReportRelay(RelayInfo):
    changed: bool = False
    TypeName: Literal["gridworks.dummy.report.relay"] = "gridworks.dummy.report.relay"


class SetRelayMessage(Message[SetRelay]):
    def __init__(
        self,
        *,
        src: str,
        relay_name: str,
        closed: bool,
        dst: str = "",
        ack_required: bool = False,
    ) -> None:
        super().__init__(
            Src=src,
            Dst=dst,
            AckRequired=ack_required,
            Payload=SetRelay(relay_name=relay_name, closed=closed),
        )
