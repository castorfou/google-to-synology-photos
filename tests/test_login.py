"""Logging in to the NAS: what the user is asked, and what is kept where."""

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from google_to_synology_photos.dsm import (
    OTP_REQUIRED,
    WRONG_OTP,
    WRONG_PASSWORD,
    LoginError,
)
from google_to_synology_photos.login import LoginFailedError, login


URL = "https://nas.local:5001"
ACCOUNT = "household"
PASSWORD = "s3cret-Passw0rd"  # pragma: allowlist secret
OTP = "123456"
CERTIFICATE = "-----BEGIN CERTIFICATE-----\nSYNTHETIC\n-----END CERTIFICATE-----\n"


class MemorySecrets:
    """The OS keyring, in memory."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)


class ScriptedUser:
    """Answers the questions in order, and records them."""

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.questions: list[str] = []

    def _answer(self, question: str) -> str:
        self.questions.append(question)
        if not self.answers:
            pytest.fail(f"unexpected question: {question}")
        return self.answers.pop(0)

    ask = _answer
    ask_secret = _answer

    def confirm(self, question: str) -> bool:
        return self._answer(question) == "yes"


@dataclass
class FakeSession:
    nas: "FakeNas"
    certificate: str | None
    logged_in: bool = False

    def login(
        self,
        account: str,
        password: str,
        otp: str | None = None,
        device_id: str | None = None,
    ) -> str | None:
        if (account, password) != (ACCOUNT, self.nas.password):
            raise LoginError(WRONG_PASSWORD)
        trusted = device_id in self.nas.devices
        if self.nas.two_factor and not trusted:
            if otp is None:
                raise LoginError(OTP_REQUIRED)
            if otp != OTP:
                raise LoginError(WRONG_OTP)
        self.logged_in = True
        if trusted:
            return device_id
        device = f"device-{len(self.nas.devices) + 1}"
        self.nas.devices.append(device)
        return device


@dataclass
class FakeNas:
    """A NAS as seen by the login: its certificate and its accounts."""

    two_factor: bool = False
    self_signed: bool = False
    password: str = PASSWORD
    devices: list[str] = field(default_factory=list)
    sessions: list[FakeSession] = field(default_factory=list)

    def certificate(self, url: str) -> str | None:
        return CERTIFICATE if self.self_signed else None

    def open(self, url: str, certificate: str | None) -> FakeSession:
        assert url == URL
        session = FakeSession(self, certificate)
        self.sessions.append(session)
        return session


@pytest.fixture
def config(tmp_path: Path) -> Path:
    return tmp_path / "config"


def test_first_run_asks_once_and_later_runs_ask_nothing(config: Path) -> None:
    nas, secrets = FakeNas(), MemorySecrets()

    first = login(config, secrets, ScriptedUser(URL, ACCOUNT, PASSWORD), nas)
    later = login(config, secrets, ScriptedUser(), nas)

    assert first.logged_in
    assert later.logged_in


def test_with_2fa_the_code_is_asked_once_then_the_device_token_is_used(
    config: Path,
) -> None:
    nas, secrets = FakeNas(two_factor=True), MemorySecrets()
    user = ScriptedUser(URL, ACCOUNT, PASSWORD, OTP)

    login(config, secrets, user, nas)
    later = login(config, secrets, ScriptedUser(), nas)

    assert any("2FA" in q for q in user.questions)
    assert later.logged_in


def test_the_password_is_never_written_to_a_file(config: Path, tmp_path: Path) -> None:
    secrets = MemorySecrets()

    login(
        config,
        secrets,
        ScriptedUser(URL, ACCOUNT, PASSWORD, OTP),
        FakeNas(two_factor=True),
    )

    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files, "the NAS address and user name are kept in a file"
    assert all(PASSWORD not in p.read_text(encoding="utf-8") for p in files)
    assert PASSWORD in secrets.values.values()


def test_a_wrong_password_stops_and_is_asked_again_next_time(config: Path) -> None:
    nas, secrets = FakeNas(), MemorySecrets()
    login(config, secrets, ScriptedUser(URL, ACCOUNT, PASSWORD), nas)
    nas.password = "changed-on-the-NAS"  # pragma: allowlist secret

    with pytest.raises(LoginFailedError):
        login(config, secrets, ScriptedUser(), nas)
    again = login(config, secrets, ScriptedUser("changed-on-the-NAS"), nas)

    assert again.logged_in


def test_a_wrong_2fa_code_stops(config: Path) -> None:
    with pytest.raises(LoginFailedError):
        login(
            config,
            MemorySecrets(),
            ScriptedUser(URL, ACCOUNT, PASSWORD, "000000"),
            FakeNas(two_factor=True),
        )


def test_a_self_signed_certificate_is_trusted_once_then_pinned(config: Path) -> None:
    nas, secrets = FakeNas(self_signed=True), MemorySecrets()
    user = ScriptedUser(URL, ACCOUNT, "yes", PASSWORD)

    login(config, secrets, user, nas)
    later = login(config, secrets, ScriptedUser(), nas)

    assert any("SHA-256" in q for q in user.questions)
    assert later.certificate == CERTIFICATE


def test_a_refused_certificate_stops_before_the_password(config: Path) -> None:
    user = ScriptedUser(URL, ACCOUNT, "no")

    with pytest.raises(LoginFailedError):
        login(config, MemorySecrets(), user, FakeNas(self_signed=True))

    assert not any("assword" in q for q in user.questions)


def test_login_again_forgets_what_was_kept(config: Path) -> None:
    nas, secrets = FakeNas(), MemorySecrets()
    login(config, secrets, ScriptedUser(URL, ACCOUNT, PASSWORD), nas)

    again = login(
        config, secrets, ScriptedUser(URL, ACCOUNT, PASSWORD), nas, ask_again=True
    )

    assert again.logged_in
