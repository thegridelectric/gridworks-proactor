from pydantic import BaseModel
from pydantic_settings import BaseSettings
from pydantic import model_validator
from pydantic import field_validator

from gwproactor.config.logging import LoggingSettings
from gwproactor.config.mqtt import MQTTClient
from gwproactor.config.paths import Paths
from typing_extensions import Self


MQTT_LINK_POLL_SECONDS = 60.0
ACK_TIMEOUT_SECONDS = 5.0
NUM_INITIAL_EVENT_REUPLOADS: int = 5


class ProactorSettings(BaseSettings):
    paths: Paths = None
    logging: LoggingSettings = LoggingSettings()
    mqtt_link_poll_seconds: float = MQTT_LINK_POLL_SECONDS
    ack_timeout_seconds: float = ACK_TIMEOUT_SECONDS
    num_initial_event_reuploads: int = NUM_INITIAL_EVENT_REUPLOADS

    class Config:
        env_prefix = "PROACTOR_"
        env_nested_delimiter = "__"

    @field_validator("paths", mode="before")
    @classmethod
    def get_paths(cls, v: Paths) -> Paths:
        if v is None:
            v = Paths()
        return v

    @classmethod
    def update_paths_name(cls, values: dict, name: str) -> dict:
        """Update paths member with a new 'name' attribute, e.g., a name known by a derived class.

        This is meant to be called in a 'mode="before"' root validator of a derived class.
        """
        if "paths" not in values:
            values["paths"] = Paths(name=name)
        else:
            if isinstance(values["paths"], BaseModel):
                if "name" not in values["paths"].model_fields_set:
                    values["paths"] = values["paths"].model_copy(name=name, deep=True) # Office hours: check model_copy works as expected
            else:
                if "name" not in values["paths"]:
                    values["paths"]["name"] = name
        return values

    @model_validator(mode="after")
    def post_root_validator(self) -> Self:
        """Update unset paths of any member MQTTClient's TLS paths based on ProactorSettings 'paths' member."""
        if not isinstance(self.paths, Paths):
            raise ValueError(
                f"ERROR. 'paths' member must be instance of Paths. Got: {type(self.paths)}"
            )
        # Office Hours: fix below
        # for k, v in values.items():
        #     if isinstance(v, MQTTClient):
        #         v.update_tls_paths(values["paths"].certs_dir, k)
        # return values
