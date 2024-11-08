import uuid
from typing import Literal

from gwproto.messages import EventBase
from pydantic import BaseModel, Field

from gwproactor_test.dummies.tree.messages import RelayInfo


class AdminInfo(BaseModel):
    User: str
    SrcMachine: str


class AdminCommandSetRelay(BaseModel):
    CommandInfo: AdminInfo
    RelayInfo: RelayInfo
    MessageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    TypeName: Literal["gridworks.dummy.admin.command.set.relay"] = (
        "gridworks.dummy.admin.command.set.relay"
    )


class AdminCommandReadRelays(BaseModel):
    CommandInfo: AdminInfo
    MessageId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    TypeName: Literal["gridworks.dummy.admin.command.read.relays"] = (
        "gridworks.dummy.admin.command.read.relays"
    )


class AdminSetRelayEvent(EventBase):
    command: AdminCommandSetRelay
    TypeName: Literal["gridworks.event.admin.command.set.relay"] = (
        "gridworks.event.admin.command.set.relay"
    )
