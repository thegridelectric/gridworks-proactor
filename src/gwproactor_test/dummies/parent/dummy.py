"""Scada implementation"""

from typing import Optional, cast

from gwproto import MQTTCodec, MQTTTopic, create_message_model

from gwproactor.links import QOS
from gwproactor.message import Message
from gwproactor.persister import SimpleDirectoryWriter
from gwproactor.proactor_implementation import Proactor
from gwproactor_test.dummies.names import (
    CHILD_SHORT_NAME,
    DUMMY_CHILD_NAME,
    DUMMY_PARENT_NAME,
    PARENT_SHORT_NAME,
)
from gwproactor_test.dummies.parent.config import DummyParentSettings


class ParentMQTTCodec(MQTTCodec):
    def __init__(self) -> None:
        super().__init__(
            create_message_model(
                model_name="ParentMessageDecoder",
                module_names=["gwproto.messages", "gwproactor.message"],
            )
        )

    def validate_source_and_destination(self, src: str, dst: str) -> None:
        if src != DUMMY_CHILD_NAME or dst != PARENT_SHORT_NAME:
            raise ValueError(
                "ERROR validating src and/or dst\n"
                f"  exp: {DUMMY_CHILD_NAME} -> {PARENT_SHORT_NAME}\n"
                f"  got: {src} -> {dst}"
            )


class DummyParent(Proactor):
    CHILD_MQTT = "child"

    def __init__(
        self,
        name: str = "",
        settings: Optional[DummyParentSettings] = None,
    ) -> None:
        super().__init__(
            name=name or DUMMY_PARENT_NAME,
            settings=DummyParentSettings() if settings is None else settings,
        )
        self._links.add_mqtt_link(
            client_name=self.CHILD_MQTT,
            destination_short_name=CHILD_SHORT_NAME,
            mqtt_config=self.settings.child_mqtt,
            codec=ParentMQTTCodec(),
            primary_peer=True,
        )
        self._links.subscribe(
            self.CHILD_MQTT,
            MQTTTopic.encode_subscription(
                Message.type_name(), DUMMY_CHILD_NAME, PARENT_SHORT_NAME
            ),
            QOS.AtMostOnce,
        )

    @classmethod
    def make_event_persister(
        cls, settings: DummyParentSettings
    ) -> SimpleDirectoryWriter:
        return SimpleDirectoryWriter(settings.paths.event_dir)

    @property
    def publication_name(self) -> str:
        return self.name

    @property
    def settings(self) -> DummyParentSettings:
        return cast(DummyParentSettings, self._settings)
