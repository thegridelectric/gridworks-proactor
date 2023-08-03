from pathlib import Path
from typing import Dict
from typing import Optional

import xdg
from pydantic import BaseModel
from pydantic import validator


DEFAULT_BASE_NAME = "gridworks"
DEFAULT_BASE_DIR = Path(DEFAULT_BASE_NAME)
DEFAULT_NAME = "scada"
DEFAULT_NAME_DIR = Path(DEFAULT_NAME)
DEFAULT_LAYOUT_FILE = Path("hardware-layout.json")


class TLSPaths(BaseModel):
    ca_cert_path: Optional[str | Path] = None
    cert_path: Optional[str | Path] = None
    private_key_path: Optional[str | Path] = None

    @classmethod
    def defaults(cls, certs_dir: Path, client_name: str) -> "TLSPaths":
        """Calcuate defaults given a certs_dir and client name. Meant to be called in context where those are known,
        e.g. a validator on a higher-level model which has access to a Paths object and a named MQTT configuration.
        """
        client_dir = Path(certs_dir) / client_name
        return TLSPaths(
            ca_cert_path=client_dir / "ca.crt",
            cert_path=client_dir / f"{client_name}.crt",
            private_key_path=client_dir / "private" / f"{client_name}.pem",
        )

    def effective_paths(self, certs_dir: Path, client_name: str) -> "TLSPaths":
        """Re-calculate non-set paths given a certs_dir and client name. Meant to be called in context where those are
        known, e.g. a validator on a higher-level model which has access to a Paths object and a named MQTT
        configuration."""
        fields = self.defaults(Path(certs_dir), client_name).dict()
        fields.update(self.dict(exclude_none=True))
        return TLSPaths(**fields)

    def mkdirs(self, mode: int = 0o777, parents: bool = True, exist_ok: bool = True):
        """Create directories that will be used to store certificates and private keys."""
        if (
            self.ca_cert_path is None
            or self.cert_path is None
            or self.private_key_path is None
        ):
            raise ValueError(
                "ERROR. TLSPaths.mkdirs() requires all paths to nave non-None values. "
                f"Current values: {self.dict()}"
            )
        self.ca_cert_path.parent.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        self.cert_path.parent.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        self.private_key_path.parent.mkdir(
            mode=mode, parents=parents, exist_ok=exist_ok
        )


class Paths(BaseModel):
    # Relative offsets used under home directories
    base: Path | str = DEFAULT_BASE_DIR
    name: Path | str = DEFAULT_NAME_DIR
    relative_path: str | Path = ""

    # Home directories (defaulting to https://specifications.freedesktop.org/basedir-spec/latest/)
    data_home: str | Path = ""
    state_home: str | Path = ""
    config_home: str | Path = ""

    # Base working paths, defaulting to xdg home/relative_path/...
    data_dir: str | Path = ""
    config_dir: str | Path = ""
    certs_dir: str | Path = ""
    event_dir: str | Path = ""
    log_dir: str | Path = ""
    hardware_layout: str | Path = ""

    @validator("data_home", always=True)
    def get_data_home(cls, v: str | Path) -> Path:
        return Path(v if v else xdg.xdg_data_home())

    @validator("state_home", always=True)
    def get_state_home(cls, v: str | Path) -> Path:
        return Path(v if v else xdg.xdg_state_home())

    @validator("config_home", always=True)
    def get_config_home(cls, v: str | Path) -> Path:
        return Path(v if v else xdg.xdg_config_home())

    @validator("config_dir", always=True)
    def get_config_dir(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["config_home"]) / values["relative_path"]
        return Path(v)

    @validator("certs_dir", always=True)
    def get_certs_dir(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["config_dir"]) / "certs"
        return Path(v)

    @validator("data_dir", always=True)
    def get_data_dir(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["data_home"]) / values["relative_path"]
        return Path(v)

    @validator("event_dir", always=True)
    def get_event_dir(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["data_dir"]) / "event"
        return Path(v)

    @validator("log_dir", always=True)
    def get_log_dir(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["state_home"]) / values["relative_path"] / "log"
        return Path(v)

    @validator("hardware_layout", always=True)
    def get_hardware_layout(cls, v, values):
        if not v:
            v = Path(values["config_dir"]) / DEFAULT_LAYOUT_FILE
        return Path(v)

    @validator("relative_path", always=True)
    def get_relative_path(cls, v: str | Path, values: Dict[str, Path | str]) -> Path:
        if not v:
            v = Path(values["base"]) / values["name"]
        return Path(v)

    def mkdirs(self, mode: int = 0o777, parents: bool = True, exist_ok: bool = True):
        self.data_dir.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        self.config_dir.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        self.event_dir.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)
        self.log_dir.mkdir(mode=mode, parents=parents, exist_ok=exist_ok)

    def copy(self, **kwargs) -> "Paths":
        fields = self.dict(exclude_unset=True)
        fields.update(**kwargs)
        return Paths(**fields)
