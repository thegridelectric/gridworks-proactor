from typing import Optional

from gwproto import Decoders
from gwproto import Message
from gwproto import MQTTCodec
from gwproto import MQTTTopic
from gwproto import create_message_payload_discriminator

from gwproactor import ProactorSettings
from gwproactor.external_watchdog import SystemDWatchdogCommandBuilder
from gwproactor.links import QOS
from gwproactor.persister import TimedRollingFilePersister
from gwproactor.proactor_implementation import Proactor
from gwproactor_test.dummies.child.config import DummyChildSettings
from gwproactor_test.dummies.names import DUMMY_CHILD_NAME
from gwproactor_test.dummies.names import DUMMY_PARENT_NAME


ChildMessageDecoder = create_message_payload_discriminator(
    "ChildMessageDecoder",
    [
        "gwproto.messages",
        "gwproactor.message",
    ],
)


class ChildMQTTCodec(MQTTCodec):
    def __init__(self):
        super().__init__(
            Decoders.from_objects(message_payload_discriminator=ChildMessageDecoder)
        )

    def validate_source_alias(self, source_alias: str):
        if source_alias != DUMMY_PARENT_NAME:
            raise Exception(
                f"alias {source_alias} not my AtomicTNode ({DUMMY_PARENT_NAME})!"
            )


class DummyChild(Proactor):
    PARENT_MQTT = "gridworks"

    def __init__(
        self,
        name: str = "",
        settings: Optional[DummyChildSettings] = None,
    ):
        super().__init__(
            name=name if name else DUMMY_CHILD_NAME,
            settings=DummyChildSettings() if settings is None else settings,
        )
        self._links.add_mqtt_link(
            DummyChild.PARENT_MQTT,
            settings.parent_mqtt,
            ChildMQTTCodec(),
            upstream=True,
            primary_peer=True,
        )
        for topic in [
            MQTTTopic.encode_subscription(Message.type_name(), DUMMY_PARENT_NAME),
            # Enable awaiting_setup edge case testing, which depends on receiving multiple, separate
            # MQTT topic subscription acks:
            MQTTTopic.encode_subscription(Message.type_name(), "1"),
            MQTTTopic.encode_subscription(Message.type_name(), "2"),
        ]:
            self._links.subscribe(self.PARENT_MQTT, topic, QOS.AtMostOnce)
        self._links.log_subscriptions("construction")

    @classmethod
    def make_event_persister(
        cls, settings: ProactorSettings
    ) -> TimedRollingFilePersister:
        return TimedRollingFilePersister(
            settings.paths.event_dir,
            pat_watchdog_args=SystemDWatchdogCommandBuilder.default_pat_args(),
        )

    @property
    def publication_name(self) -> str:
        return self.name

    @property
    def settings(self):
        return self._settings
