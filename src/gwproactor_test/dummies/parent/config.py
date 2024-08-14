from typing import Any
from typing import Optional

from pydantic import model_validator

from gwproactor import ProactorSettings
from gwproactor.config import LoggingSettings
from gwproactor.config import MQTTClient
from gwproactor.config import Paths
from gwproactor_test.dummies.names import DUMMY_PARENT_ENV_PREFIX
from gwproactor_test.dummies.names import DUMMY_PARENT_NAME


class DummyParentSettings(ProactorSettings):
    child_mqtt: MQTTClient = MQTTClient()

    class Config(ProactorSettings.Config):
        env_prefix = DUMMY_PARENT_ENV_PREFIX

    @model_validator(mode="before")
    def pre_root_validator(cls, values: dict) -> dict:
        return ProactorSettings.update_paths_name(values, DUMMY_PARENT_NAME)
