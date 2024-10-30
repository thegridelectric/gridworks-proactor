import typing
from collections import defaultdict
from typing import Optional

import rich
from gwproto import Message

from gwproactor import Proactor
from gwproactor.links.link_settings import LinkSettings
from gwproactor.message import MQTTReceiptPayload
from gwproactor.persister import SimpleDirectoryWriter
from gwproactor_test.dummies.names import DUMMY_SCADA2_SHORT_NAME
from gwproactor_test.dummies.tree.codecs import DummyCodec
from gwproactor_test.dummies.tree.messages import (
    ReportRelay,
    SetRelay,
    SetRelayMessage,
)
from gwproactor_test.dummies.tree.scada2_settings import DummyScada2Settings


class DummyScada2(Proactor):
    relays: dict[str, bool]

    def __init__(
        self,
        name: str = "",
        settings: Optional[DummyScada2Settings] = None,
    ) -> None:
        if settings is None:
            settings = DummyScada2Settings()
        self.relays = defaultdict(bool)
        super().__init__(name=name, settings=settings)
        self._links.add_mqtt_link(
            LinkSettings(
                client_name=self.settings.scada1_link.client_name,
                gnode_name=self.settings.scada1_link.long_name,
                spaceheat_name=self.settings.scada1_link.short_name,
                mqtt=self.settings.scada1_link,
                codec=DummyCodec(
                    src_name=self.settings.scada1_link.long_name,
                    dst_name=DUMMY_SCADA2_SHORT_NAME,
                    model_name="Scada1ToScada2Message",
                ),
                upstream=True,
            ),
        )
        self.links.log_subscriptions("construction")

    @property
    def settings(self) -> DummyScada2Settings:
        return typing.cast(DummyScada2Settings, self._settings)

    @property
    def subscription_name(self) -> str:
        return DUMMY_SCADA2_SHORT_NAME

    @classmethod
    def make_event_persister(
        cls, settings: DummyScada2Settings
    ) -> SimpleDirectoryWriter:
        return SimpleDirectoryWriter(settings.paths.event_dir)

    def _process_set_relay(self, message: SetRelayMessage) -> None:
        self._logger.path(
            f"++{self.name}._process_set_relay "
            f"{message.Payload.relay_name}  "
            f"closed:{message.Payload.closed}"
        )
        path_dbg = 0
        last_val = self.relays[message.Payload.relay_name]
        report = ReportRelay(
            relay_name=message.Payload.relay_name,
            closed=message.Payload.closed,
            changed=last_val != message.Payload.closed,
        )
        if report.changed:
            path_dbg |= 0x00000001
            self.relays[message.Payload.relay_name] = report.closed
        self._links.publish_upstream(report)
        self._logger.path(
            f"--{self.name}._process_set_relay  "
            f"path:0x{path_dbg:08X}  "
            f"{int(last_val)} -> "
            f"{int(report.closed)}"
        )

    def _derived_process_mqtt_message(
        self, message: Message[MQTTReceiptPayload], decoded: typing.Any
    ) -> None:
        self._logger.path(
            f"++{self.name}._derived_process_mqtt_message {message.Payload.message.topic}",
        )
        path_dbg = 0
        match decoded.Payload:
            case SetRelay():
                path_dbg |= 0x00000001
                self._process_set_relay(decoded)
            case _:
                path_dbg |= 0x00000008
                rich.print(decoded.Header)
                raise ValueError(
                    f"There is no handler for mqtt message payload type [{type(decoded.Payload)}]\n"
                    f"Received\n\t topic: [{message.Payload.message.topic}]"
                )
        self._logger.path(
            f"--{self.name}._derived_process_mqtt_message  path:0x{path_dbg:08X}",
        )
