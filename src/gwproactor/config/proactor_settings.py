from pydantic import BaseSettings
from pydantic import validator

from gwproactor.config.logging import LoggingSettings
from gwproactor.config.paths import Paths


MQTT_LINK_POLL_SECONDS = 60.0
ACK_TIMEOUT_SECONDS = 5.0


class ProactorSettings(BaseSettings):
    paths: Paths = None
    logging: LoggingSettings = LoggingSettings()
    mqtt_link_poll_seconds: float = MQTT_LINK_POLL_SECONDS
    ack_timeout_seconds: float = ACK_TIMEOUT_SECONDS

    class Config:
        env_prefix = "PROACTOR_"
        env_nested_delimiter = "__"

    @validator("paths", always=True)
    def get_paths(cls, v: Paths) -> Paths:
        if v is None:
            v = Paths()
        return v
