from pydantic import BaseSettings
from pydantic import validator

from gwproactor.config.logging import LoggingSettings
from gwproactor.config.mqtt import MQTTClient
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

    @classmethod
    def update_paths_name(cls, values: dict, name: str) -> dict:
        """Update paths member with a new 'name' attribute, e.g., a name known by a derived class.

        This is meant to be called in a 'pre=True' root validator of a derived class.
        """
        if "paths" not in values:
            values["paths"] = Paths(name=name)
        elif "name" not in values["paths"].__fields_set__:
            values["paths"] = values["paths"].copy(name=name)
        return values

    @classmethod
    def update_tls_paths(cls, values: dict, proactor_name: str = "") -> dict:
        """Update unset paths of any member MQTTClient's TLS paths based on ProactorSettings 'paths' member.

        This is meant to be called in a root validator of a derived class.
        """
        if not isinstance(values["paths"], Paths):
            raise ValueError(
                f"ERROR. 'paths' member must be instance of Paths. Got: {type(values['paths'])}"
            )
        for k, v in values.items():
            if isinstance(v, MQTTClient):
                v.update_tls_paths(values["paths"].certs_dir, k)
        return values
