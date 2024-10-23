from gwproto import Message, MQTTCodec, MQTTTopic

from gwproactor.config import MQTTClient


class LinkSettings:
    client_name: str
    gnode_name: str
    spaceheat_name: str
    upstream: bool
    mqtt: MQTTClient
    codec: MQTTCodec
    primary_peer: bool = False

    def __init__(  # noqa: PLR0913
        self,
        *,
        client_name: str,
        gnode_name: str,
        spaceheat_name: str,
        upstream: bool,
        mqtt: MQTTClient,
        codec: MQTTCodec,
        primary_peer: bool = False,
    ) -> None:
        self.client_name = client_name
        self.gnode_name = gnode_name
        self.spaceheat_name = spaceheat_name
        self.upstream = upstream
        self.mqtt = mqtt
        self.codec = codec
        self.primary_peer = primary_peer

    def subscription_topic(self, receiver_spaceheat_name: str) -> str:
        return MQTTTopic.encode(
            envelope_type=Message.type_name(),
            src=self.gnode_name,
            dst=receiver_spaceheat_name,
            message_type="#",
        )
