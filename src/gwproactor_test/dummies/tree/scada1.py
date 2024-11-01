import typing
from collections import defaultdict
from typing import Optional

import rich
from gwproto import Message
from gwproto.messages import EventBase

from gwproactor import Proactor
from gwproactor.links.link_settings import LinkSettings
from gwproactor.message import MQTTReceiptPayload
from gwproactor.persister import SimpleDirectoryWriter
from gwproactor_test.dummies.names import DUMMY_SCADA1_SHORT_NAME
from gwproactor_test.dummies.tree.codecs import DummyCodec
from gwproactor_test.dummies.tree.messages import (
    RelayReportEvent,
    RelayReportReceivedEvent,
    SetRelay,
    SetRelayMessage,
)
from gwproactor_test.dummies.tree.scada1_settings import DummyScada1Settings


class DummyScada1(Proactor):
    relays: dict[str, bool]
    relay_change_mimatches: int

    def __init__(
        self,
        name: str = "",
        settings: Optional[DummyScada1Settings] = None,
    ) -> None:
        if settings is None:
            settings = DummyScada1Settings()
        self.relays = defaultdict(bool)
        self.relay_change_mimatches = 0
        super().__init__(name=name, settings=settings)

        self._links.add_mqtt_link(
            LinkSettings(
                client_name=self.settings.atn_link.client_name,
                gnode_name=self.settings.atn_link.long_name,
                spaceheat_name=self.settings.atn_link.short_name,
                mqtt=self.settings.atn_link,
                codec=DummyCodec(
                    src_name=self.settings.atn_link.long_name,
                    dst_name=DUMMY_SCADA1_SHORT_NAME,
                    model_name="Atn1ToScada1Message",
                ),
                upstream=True,
            ),
        )
        self._links.add_mqtt_link(
            LinkSettings(
                client_name=self.settings.scada2_link.client_name,
                gnode_name=self.settings.scada2_link.long_name,
                spaceheat_name=self.settings.scada2_link.short_name,
                mqtt=self.settings.scada2_link,
                codec=DummyCodec(
                    src_name=self.settings.scada2_link.long_name,
                    dst_name=DUMMY_SCADA1_SHORT_NAME,
                    model_name="Scada2ToScada1Message",
                ),
                downstream=True,
            ),
        )
        self.links.log_subscriptions("construction")

    @property
    def settings(self) -> DummyScada1Settings:
        return typing.cast(DummyScada1Settings, self._settings)

    @property
    def subscription_name(self) -> str:
        return DUMMY_SCADA1_SHORT_NAME

    @classmethod
    def make_event_persister(
        cls, settings: DummyScada1Settings
    ) -> SimpleDirectoryWriter:
        return SimpleDirectoryWriter(settings.paths.event_dir)

    def set_relay(self, relay_name: str, closed: bool) -> None:
        self.send_threadsafe(
            SetRelayMessage(
                src=self.name,
                dst=self.name,
                relay_name=relay_name,
                closed=closed,
            )
        )

    def _derived_process_message(self, message: Message) -> None:
        self._logger.path(
            f"++{self.name}._derived_process_message "
            f"{message.Header.Src}/{message.Header.MessageType}"
        )
        path_dbg = 0
        match message.Payload:
            case SetRelay():
                path_dbg |= 0x00000001
                self._links.publish_message(
                    self.downstream_client,
                    SetRelayMessage(
                        src=self.publication_name,
                        relay_name=message.Payload.relay_name,
                        closed=message.Payload.closed,
                        ack_required=True,
                    ),
                )
            case _:
                path_dbg |= 0x00000002
        self._logger.path(
            "--{self.name}._derived_process_message  path:0x{path_dbg:08X}"
        )

    def _process_report_relay_event(self, event: RelayReportEvent) -> None:
        self._logger.path(
            f"++{self.name}._process_set_relay_event "
            f"{event.relay_name}  "
            f"closed:{event.closed}  "
            f"changed: {event.changed}"
        )
        path_dbg = 0
        last_val = self.relays[event.relay_name]
        self.relays[event.relay_name] = event.closed
        changed = last_val != self.relays[event.relay_name]
        self.logger.info(
            f"{event.relay_name}:  {int(last_val)} -> "
            f"{int(self.relays[event.relay_name])}  "
            f"changed: {int(changed)}/{int(event.changed)}"
        )
        report_received_event = RelayReportReceivedEvent(
            relay_name=event.relay_name,
            closed=event.closed,
            changed=event.changed,
        )

        if changed != event.changed:
            path_dbg |= 0x00000001
            report_received_event.mismatch = True
            self.relay_change_mimatches += 1
            report_received_event.mismatch_count = self.relay_change_mimatches
            self.logger.info(
                f"State change mismatch for {event.relay_name}  "
                f"found: {int(changed)}  reported: {event.changed}  "
                f"total mismatches: {self.relay_change_mimatches}"
            )
        self.generate_event(report_received_event)
        self._logger.path(
            f"--{self.name}._process_set_relay_event "
            f"{event.relay_name}  "
            f"closed:{event.closed}  "
            f"changed: {event.changed}  "
            f"path: 0x{path_dbg:08X}"
        )

    def _process_event(self, event: EventBase) -> None:
        self._logger.path(
            f"++_process_event  {event.TypeName}  from:{event.Src}",
        )
        self.generate_event(event)  # noqa: ERA001
        if isinstance(event, RelayReportEvent):
            self._process_report_relay_event(event)
        self._logger.path("--_process_event")

    def _derived_process_mqtt_message(
        self, message: Message[MQTTReceiptPayload], decoded: Message[typing.Any]
    ) -> None:
        self._logger.path(
            f"++{self.name}._derived_process_mqtt_message {message.Payload.message.topic}",
        )
        path_dbg = 0
        match decoded.Payload:
            case EventBase():
                path_dbg |= 0x00000001
                self._process_event(decoded.Payload)
            case _:
                path_dbg |= 0x00000002
                rich.print(decoded.Header)
                raise ValueError(
                    f"There is no handler for mqtt message payload type [{type(decoded.Payload)}]\n"
                    f"Received\n\t topic: [{message.Payload.message.topic}]"
                )
        self._logger.path(
            f"--{self.name}._derived_process_mqtt_message  path:0x{path_dbg:08X}",
        )
