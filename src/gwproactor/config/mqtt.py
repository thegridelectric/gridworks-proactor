import ssl
from pathlib import Path
from ssl import VerifyMode
from typing import Optional

from pydantic import BaseModel
from pydantic import SecretStr

from gwproactor.config.paths import TLSPaths


class TLSInfo(BaseModel):
    use_tls: bool = False
    paths: TLSPaths = TLSPaths()
    cert_reqs: Optional[VerifyMode] = ssl.CERT_REQUIRED
    ciphers: Optional[str] = None
    keyfile_password: SecretStr = SecretStr("")

    def get_effective_tls_info(self, config_dir: Path) -> "TLSInfo":
        return TLSInfo(
            **dict(self.dict(), paths=self.paths.effective_paths(config_dir))
        )


class MQTTClient(BaseModel):
    """Settings for connecting to an MQTT Broker"""

    host: str = "localhost"
    port: int = 1883
    keepalive: int = 60
    bind_address: str = ""
    bind_port: int = 0
    username: Optional[str] = None
    password: SecretStr = SecretStr("")
    tls: TLSInfo = TLSInfo()

    def get_effective_tls(self, config_dir: Path) -> TLSInfo:
        return self.tls.get_effective_tls_info(config_dir)
