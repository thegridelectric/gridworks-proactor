"""Generate or copy test certificates for MQTT using TLS."""
import os
import shutil
import subprocess
from pathlib import Path

from gwcert import DEFAULT_CA_DIR  # noqa

from gwproactor.config.paths import TLSPaths


TEST_CA_CERTIFICATE_PATH_VAR = "GWPROACTOR_TEST_CA_CERT_PATH"
TEST_CA_CERTIFICATE_PATH = DEFAULT_CA_DIR / "ca.crt"
TEST_CA_CERTIFICATE_KEY_VAR = "GWPROACTOR_TEST_CA_KEY_PATH"
TEST_CA_PRIVATE_KEY_PATH = DEFAULT_CA_DIR / "private" / "ca_key.pem"


def _key_path(tag: str, var_name: str, default: Path) -> Path:
    """Return the path to a specified key, specified by environment variable or default. Raise an
    error if that a file that path does not exist."""
    env_val = os.getenv(var_name)
    if env_val:
        key_path = Path(env_val)
        if not key_path.exists():
            raise ValueError(
                f"ERROR. Key <{tag}> does not exist at path: {key_path}.\n"
                f"  Key path specified via environment variable {var_name}"
            )
    else:
        key_path = default
        if not key_path.exists():
            raise ValueError(
                f"ERROR. Key <{tag}> does not exist at path: {key_path}.\n"
                f"  Key path is the default path for <{tag}> because environment variable {var_name} is empty or missing."
            )
    return key_path


def test_ca_certificate_path() -> Path:
    """Return the path to the CA certificate used in testing, specified by environment variable or default. Raise an
    error if that a file that path does not exist.
    """
    return _key_path(
        "CA certificate", TEST_CA_CERTIFICATE_PATH_VAR, TEST_CA_CERTIFICATE_PATH
    )


def test_ca_private_key_path() -> Path:
    """Return the path to the CA private key used in testing, specified by environment variable or default. Raise an
    error if that a file that path does not exist.
    """
    return _key_path(
        "CA private key", TEST_CA_CERTIFICATE_KEY_VAR, TEST_CA_PRIVATE_KEY_PATH
    )


def _copy_keys(test_cert_dir: Path, dst_paths: TLSPaths) -> None:
    ca_cert_path = test_ca_certificate_path()
    ca_private_key_path = test_ca_certificate_path()
    src_paths = TLSPaths(
        ca_cert_path=ca_cert_path,
        cert_path=test_cert_dir / "certificate.pem",
        private_key_path=test_cert_dir / "private" / "private_key.pem",
    )
    if not src_paths.cert_path.exists() or src_paths.private_key_path.exists():
        print(
            f"One or more TLS test keys at {test_cert_dir} does not exist. (Re?)creating."
        )
        print(
            f"  Cert path        exists:{str(src_paths.cert_path.exists()):5s}  {src_paths.cert_path}"
        )
        print(
            f"  Private key path exists:{str(src_paths.private_key_path.exists()):5s}  {src_paths.private_key_path}"
        )
        gwcert_command = [
            "gwcert",
            "key",
            "add",
            "--ca-certificate-path",
            ca_cert_path,
            "--ca-private-key-path",
            ca_private_key_path,
            "--force",
            src_paths.private_key_path,
        ]
        print(f"Generating keys with command:\n  {' '.join(gwcert_command)}")
        subprocess.run(gwcert_command, capture_output=True, check=True)
    dst_paths.mkdirs()
    shutil.copy2(src_paths.ca_cert_path, dst_paths.ca_cert_path)
    shutil.copy2(src_paths.cert_path, dst_paths.cert_path)
    shutil.copy2(src_paths.private_key_path, dst_paths.private_key_path)


# def copy_keys(dst_xdg_config_dir: Path):
#     _copy_keys(test_certs_dir, TLSPaths.defaults(dst_xdg_config_dir/))
