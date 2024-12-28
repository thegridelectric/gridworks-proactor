from gwproactor.config import MQTTClient


class TreeLinkSettings(MQTTClient):
    enabled: bool = True
    client_name: str = ""
    long_name: str = ""
    short_name: str = ""
