import ssl
from pathlib import Path
from ssl import VerifyMode
from typing import Optional

from pydantic import BaseModel
from pydantic import SecretStr

from gwproactor.config.paths import TLSPaths


class TLSInfo(BaseModel):
    """TLS settings for a single MQTT client"""

    use_tls: bool = False
    paths: TLSPaths = TLSPaths()
    cert_reqs: Optional[VerifyMode] = ssl.CERT_REQUIRED
    ciphers: Optional[str] = None
    keyfile_password: SecretStr = SecretStr("")

    def update_tls_paths(self, certs_dir: Path, client_name: str) -> "TLSInfo":
        """Calculate non-set paths given a certs_dir and client name. Meant to be called in context where those are
        known, e.g. a validator on a higher-level model which has access to a Paths object and a named MQTT
        configuration."""
        self.paths = self.paths.effective_paths(certs_dir, client_name)
        return self


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

    def update_tls_paths(self, certs_dir: Path, client_name: str) -> "MQTTClient":
        """Calculate non-set paths given a certs_dir and client name. Meant to be called in context where those are
        known, e.g. a validator on a higher-level model which has access to a Paths object and a named MQTT
        configuration."""
        self.tls.update_tls_paths(certs_dir, client_name)
        return self
