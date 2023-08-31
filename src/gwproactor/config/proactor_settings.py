from pydantic import BaseModel
from pydantic import BaseSettings
from pydantic import root_validator
from pydantic import validator

from gwproactor.config.logging import LoggingSettings
from gwproactor.config.mqtt import MQTTClient
from gwproactor.config.paths import Paths


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
        else:
            if isinstance(values["paths"], BaseModel):
                if "name" not in values["paths"].__fields_set__:
                    values["paths"] = values["paths"].copy(name=name, deep=True)
            else:
                if "name" not in values["paths"]:
                    values["paths"]["name"] = name
        return values

    @root_validator(skip_on_failure=True)
    def post_root_validator(cls, values: dict) -> dict:
        """Update unset paths of any member MQTTClient's TLS paths based on ProactorSettings 'paths' member."""
        if not isinstance(values["paths"], Paths):
            raise ValueError(
                f"ERROR. 'paths' member must be instance of Paths. Got: {type(values['paths'])}"
            )
        for k, v in values.items():
            if isinstance(v, MQTTClient):
                v.update_tls_paths(values["paths"].certs_dir, k)
        return values
