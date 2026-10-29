"""Logging in to the NAS as the NAS Account.

The first run asks for the NAS address, the user name and the password, plus a
2FA code when 2FA is on. Later runs ask nothing:

- the NAS address, the user name and a self-signed certificate the user
  trusted go to ``settings.json`` in the config folder;
- the password and the device token go to the OS keyring, never to a file.

DSM always needs the password; the device token only spares the 2FA code.
"""

import contextlib
import getpass
import hashlib
import json
import socket
import ssl
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import keyring
import keyring.errors

from google_to_synology_photos.dsm import (
    OTP_REQUIRED,
    WRONG_PASSWORD,
    DsmApi,
    LoginError,
    pinned_tls,
    server_certificate,
    verified_tls,
)


SETTINGS_FILE = "settings.json"
KEYRING_SERVICE = "g2s"


class LoginFailedError(Exception):
    """The login could not be made; the message says why."""


class Secrets(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class User(Protocol):
    def ask(self, question: str) -> str: ...
    def ask_secret(self, question: str) -> str: ...
    def confirm(self, question: str) -> bool: ...


class Session(Protocol):
    def login(
        self,
        account: str,
        password: str,
        otp: str | None = None,
        device_id: str | None = None,
    ) -> str | None: ...


class Gateway[S: Session](Protocol):
    def certificate(self, url: str) -> str | None:
        """Return the certificate to pin, or None if the system trusts the NAS."""
        ...

    def open(self, url: str, certificate: str | None) -> S:
        """Open a session to the NAS, trusting certificate if given."""
        ...


@dataclass
class Settings:
    nas_url: str
    account: str
    certificate: str | None = None

    def key(self, secret: str) -> str:
        """Keyring key of a secret of this NAS Account."""
        return f"{self.nas_url} {self.account} {secret}"


def login[T: Session](
    config_dir: Path,
    secrets: Secrets,
    user: User,
    gateway: Gateway[T],
    ask_again: bool = False,
) -> T:
    """Return a logged-in session, asking the user only what is not kept."""
    settings_file = config_dir / SETTINGS_FILE
    settings = None if ask_again else _load(settings_file)
    if settings is None:
        settings = _ask_settings(user, gateway)
        secrets.delete(settings.key("password"))
        secrets.delete(settings.key("device"))

    password = secrets.get(settings.key("password")) or user.ask_secret(
        f"Password of {settings.account} on the NAS: "
    )
    device = secrets.get(settings.key("device"))
    session = gateway.open(settings.nas_url, settings.certificate)
    try:
        try:
            device = session.login(settings.account, password, device_id=device)
        except LoginError as error:
            if error.code != OTP_REQUIRED:
                raise
            otp = user.ask("2FA code from your authenticator app: ")
            device = session.login(settings.account, password, otp=otp)
    except LoginError as error:
        if error.code == WRONG_PASSWORD:
            secrets.delete(settings.key("password"))
            raise LoginFailedError("Wrong user name or password.") from error
        raise LoginFailedError(
            f"The NAS refused the login (error {error.code})."
        ) from error

    secrets.set(settings.key("password"), password)
    if device:
        secrets.set(settings.key("device"), device)
    config_dir.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    return session


def _load(settings_file: Path) -> Settings | None:
    if not settings_file.exists():
        return None
    return Settings(**json.loads(settings_file.read_text(encoding="utf-8")))


def _ask_settings(user: User, gateway: Gateway[Session]) -> Settings:
    url = user.ask("NAS address, such as https://192.168.1.20:5001: ").strip()
    if not url.startswith("https://"):
        url = "https://" + url
    account = user.ask("NAS Account user name: ").strip()
    certificate = gateway.certificate(url)
    if certificate is not None:
        fingerprint = _fingerprint(certificate)
        if not user.confirm(
            "The NAS presents a certificate that this computer does not know.\n"
            f"Its SHA-256 fingerprint is {fingerprint}.\n"
            "You can compare it with the one shown in DSM, Control Panel > "
            "Security > Certificate. Trust it? (yes/no) "
        ):
            raise LoginFailedError("The NAS certificate was not trusted.")
    return Settings(url, account, certificate)


def _fingerprint(certificate_pem: str) -> str:
    try:
        der = ssl.PEM_cert_to_DER_cert(certificate_pem)
    except ValueError:
        der = certificate_pem.encode()
    digest = hashlib.sha256(der).hexdigest().upper()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


class KeyringSecrets:
    """Secrets in the OS keyring."""

    def get(self, key: str) -> str | None:
        value: str | None = keyring.get_password(KEYRING_SERVICE, key)
        return value

    def set(self, key: str, value: str) -> None:
        keyring.set_password(KEYRING_SERVICE, key, value)

    def delete(self, key: str) -> None:
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(KEYRING_SERVICE, key)


class TerminalUser:
    """Asks in the terminal; the password is not echoed."""

    def ask(self, question: str) -> str:
        return input(question)

    def ask_secret(self, question: str) -> str:
        return getpass.getpass(question)

    def confirm(self, question: str) -> bool:
        return input(question).strip().lower() in ("y", "yes")


class DsmGateway:
    """Reaches the DSM Web API of a real NAS."""

    def certificate(self, url: str) -> str | None:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname or "", parts.port or 443
        try:
            with (
                socket.create_connection((host, port), timeout=15) as raw,
                verified_tls().wrap_socket(raw, server_hostname=host),
            ):
                return None
        except ssl.SSLCertVerificationError:
            return server_certificate(url)

    def open(self, url: str, certificate: str | None) -> DsmApi:
        tls = pinned_tls(certificate) if certificate else verified_tls()
        return DsmApi(url, tls)
