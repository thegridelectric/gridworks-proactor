"""Scada implementation"""

from typing import Optional, cast

from gwproactor.links.link_settings import LinkSettings
from gwproactor.persister import SimpleDirectoryWriter
from gwproactor.proactor_implementation import Proactor
from gwproactor_test.dummies import DUMMY_ATN_NAME
from gwproactor_test.dummies.names import DUMMY_ATN_SHORT_NAME
from gwproactor_test.dummies.tree.atn_settings import DummyAtnSettings
from gwproactor_test.dummies.tree.codecs import DummyCodec


class DummyAtn(Proactor):
    def __init__(
        self,
        name: str = "",
        settings: Optional[DummyAtnSettings] = None,
    ) -> None:
        super().__init__(
            name=name or DUMMY_ATN_NAME,
            settings=DummyAtnSettings() if settings is None else settings,
        )
        self._links.add_mqtt_link(
            LinkSettings(
                client_name=self.settings.scada1_link.client_name,
                gnode_name=self.settings.scada1_link.long_name,
                spaceheat_name=self.settings.scada1_link.short_name,
                mqtt=self.settings.scada1_link,
                codec=DummyCodec(
                    src_name=self.settings.scada1_link.long_name,
                    dst_name=DUMMY_ATN_SHORT_NAME,
                    model_name="Scada1ToAtn1Message",
                ),
                downstream=True,
            ),
        )
        self.links.log_subscriptions()

    @classmethod
    def make_event_persister(cls, settings: DummyAtnSettings) -> SimpleDirectoryWriter:
        return SimpleDirectoryWriter(settings.paths.event_dir)

    @property
    def publication_name(self) -> str:
        return self.name

    @property
    def settings(self) -> DummyAtnSettings:
        return cast(DummyAtnSettings, self._settings)
