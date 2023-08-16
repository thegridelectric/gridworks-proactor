from pydantic import root_validator

from gwproactor import ProactorSettings
from gwproactor.config import MQTTClient
from gwproactor_test.dummies.names import DUMMY_CHILD_ENV_PREFIX
from gwproactor_test.dummies.names import DUMMY_CHILD_NAME


class DummyChildSettings(ProactorSettings):
    parent_mqtt: MQTTClient = MQTTClient()
    seconds_per_report: int = 300
    async_power_reporting_threshold = 0.02

    class Config(ProactorSettings.Config):
        env_prefix = DUMMY_CHILD_ENV_PREFIX

    @root_validator(pre=True)
    def pre_root_validator(cls, values: dict) -> dict:
        return ProactorSettings.update_paths_name(values, DUMMY_CHILD_NAME)
