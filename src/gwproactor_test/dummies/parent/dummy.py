"""Scada implementation"""

from typing import Optional, cast

from gwproto import MQTTCodec, MQTTTopic, create_message_model

from gwproactor.links import QOS
from gwproactor.message import Message
from gwproactor.persister import SimpleDirectoryWriter
from gwproactor.proactor_implementation import Proactor
from gwproactor_test.dummies.names import DUMMY_CHILD_NAME, DUMMY_PARENT_NAME
from gwproactor_test.dummies.parent.config import DummyParentSettings


class ParentMQTTCodec(MQTTCodec):
    def __init__(self) -> None:
        super().__init__(
            create_message_model(
                model_name="ParentMessageDecoder",
                module_names=["gwproto.messages", "gwproactor.message"],
            )
        )

    def validate_source_alias(self, source_alias: str) -> None:
        if source_alias != DUMMY_CHILD_NAME:
            raise ValueError(f"alias {source_alias} not my Scada!")


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
            self.CHILD_MQTT,
            self.settings.child_mqtt,
            ParentMQTTCodec(),
            primary_peer=True,
        )
        self._links.subscribe(
            self.CHILD_MQTT,
            MQTTTopic.encode_subscription(Message.type_name(), DUMMY_CHILD_NAME),
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
