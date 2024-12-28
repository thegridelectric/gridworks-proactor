from gwproto import MQTTCodec, create_message_model

from gwproactor_test.dummies.tree.admin_messages import (
    AdminCommandReadRelays,
    AdminCommandSetRelay,
)


class DummyCodec(MQTTCodec):
    src_name: str
    dst_name: str

    def __init__(self, src_name: str, dst_name: str, model_name: str) -> None:
        self.src_name = src_name
        self.dst_name = dst_name
        super().__init__(
            create_message_model(
                model_name=model_name,
                module_names=[
                    "gwproto.messages",
                    "gwproactor.message",
                    "gwproactor_test.dummies.tree.messages",
                ],
            )
        )

    def validate_source_and_destination(self, src: str, dst: str) -> None:
        if src != self.src_name or dst != self.dst_name:
            raise ValueError(
                "ERROR validating src and/or dst\n"
                f"  exp: {self.src_name} -> {self.dst_name}\n"
                f"  got: {src} -> {dst}"
            )


class AdminCodec(MQTTCodec):
    def __init__(self) -> None:
        super().__init__(
            create_message_model(
                model_name="AdminMessageDecoder",
                explicit_types=[AdminCommandSetRelay, AdminCommandReadRelays],
            )
        )

    def validate_source_and_destination(self, src: str, dst: str) -> None: ...
