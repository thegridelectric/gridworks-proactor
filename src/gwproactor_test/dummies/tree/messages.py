import uuid
from typing import Literal

from gwproto import Message
from gwproto.messages import EventBase
from pydantic import BaseModel, Field


class RelayInfo(BaseModel):
    relay_name: str = ""
    closed: bool = False


class SetRelay(RelayInfo):
    MessageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    TypeName: Literal["gridworks.dummy.set.relay"] = "gridworks.dummy.set.relay"


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


class RelayReportEvent(EventBase):
    """Dummy event, scada2 -> scada1"""

    relay_name: str = ""
    closed: bool = False
    changed: bool = False
    TypeName: Literal["gridworks.event.relay.report"] = "gridworks.event.relay.report"


class RelayReportReceivedEvent(RelayReportEvent):
    """Dummy event, scada1 *received* RelayReportEvent"""

    mismatch: bool = False
    mismatch_count: int = 0
    TypeName: Literal["gridworks.event.relay.report.received"] = (
        "gridworks.event.relay.report.received"
    )
