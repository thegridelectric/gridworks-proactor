from gwproactor.config import MQTTClient


class TreeLinkSettings(MQTTClient):
    client_name: str = ""
    long_name: str = ""
    short_name: str = ""
