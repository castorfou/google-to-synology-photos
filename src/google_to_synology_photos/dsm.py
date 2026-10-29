"""Transport to the DSM Web API of the NAS: login, calls and file uploads."""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
from typing import Any

from google_to_synology_photos.synology import SynologyError


# SYNO.API.Auth error codes.
WRONG_PASSWORD = 400
OTP_REQUIRED = 403
WRONG_OTP = 404
DEVICE_NAME = "g2s"


class LoginError(Exception):
    """The NAS refused the login."""

    def __init__(self, code: int) -> None:
        super().__init__(f"login refused by the NAS (error {code})")
        self.code = code


def verified_tls() -> ssl.SSLContext:
    """TLS that trusts the certificate authorities of the system."""
    return ssl.create_default_context()


def pinned_tls(certificate_pem: str) -> ssl.SSLContext:
    """TLS that trusts exactly one certificate, such as the NAS's self-signed one.

    The NAS is reached by its LAN address, which its certificate rarely names, so
    the host name is not checked: the pinned certificate is the check.
    """
    context = ssl.create_default_context(cadata=certificate_pem)
    context.check_hostname = False
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


def unverified_tls() -> ssl.SSLContext:
    """TLS with no certificate check, for the contract test on the LAN only."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def host_and_port(base_url: str) -> tuple[str, int]:
    """Return the host and port of an https URL."""
    url = urllib.parse.urlsplit(base_url)
    return url.hostname or "", url.port or 443


def server_certificate(base_url: str) -> str:
    """Return the PEM certificate the server at base_url presents."""
    return ssl.get_server_certificate(host_and_port(base_url), timeout=15)


class DsmApi:
    """A logged-in session on the DSM Web API (``/webapi/entry.cgi``)."""

    def __init__(self, base_url: str, tls: ssl.SSLContext) -> None:
        self._url = base_url.rstrip("/") + "/webapi/entry.cgi"
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=tls),
            urllib.request.HTTPCookieProcessor(CookieJar()),
        )
        self._token = ""

    def login(
        self,
        account: str,
        password: str,
        otp: str | None = None,
        device_id: str | None = None,
    ) -> str | None:
        """Log in with ``session=webui``; return the device token, if any.

        A device token lets later logins skip the 2FA code. The password is
        always needed.
        """
        params = {
            "account": account,
            "passwd": password,
            "format": "cookie",
            "enable_syno_token": "yes",
            "enable_device_token": "yes",
            "device_name": DEVICE_NAME,
        }
        if otp:
            params["otp_code"] = otp
        if device_id:
            params["device_id"] = device_id
        response = self._auth("login", params)
        if not response.get("success"):
            raise LoginError(response.get("error", {}).get("code", 0))
        data = response["data"]
        self._token = data.get("synotoken", "")
        return data.get("did") or None

    def logout(self) -> None:
        """End the session."""
        self._auth("logout", {})

    def call(
        self,
        api: str,
        method: str,
        version: int,
        plain: dict[str, str] | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        """Call api.method; params are sent JSON-encoded, plain ones as they are.

        Return the response data. Raise SynologyError when the call fails.
        """
        body = {"api": api, "method": method, "version": str(version)}
        body |= {k: json.dumps(v, ensure_ascii=False) for k, v in params.items()}
        body |= plain or {}
        return self._data(self._post(body), f"{api}.{method}")

    def upload(
        self,
        api: str,
        method: str,
        version: int,
        fields: dict[str, str],
        filename: str,
        data: bytes,
    ) -> dict[str, Any]:
        """Upload a file to api.method; fields are sent as they are, file last.

        Return the response data. Raise SynologyError when the call fails.
        """
        fields = {"api": api, "method": method, "version": str(version)} | fields
        boundary = uuid.uuid4().hex
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'
            f"{v}\r\n".encode()
            for k, v in fields.items()
        ]
        quoted = urllib.parse.quote(filename)
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f"filename=\"{quoted}\"; filename*=UTF-8''{quoted}\r\n"
            "Content-Type: application/octet-stream\r\n\r\n".encode()
            + data
            + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        request = self._request(b"".join(parts))
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        return self._data(self._send(request), f"{api}.{method}")

    def _auth(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        """Call SYNO.API.Auth for the webui session; return the raw response."""
        return self._post(
            {"api": "SYNO.API.Auth", "method": method, "version": "6"}
            | {"session": "webui"}
            | params
        )

    def _post(self, body: dict[str, str]) -> dict[str, Any]:
        """Send a form POST; return the raw response."""
        return self._send(self._request(urllib.parse.urlencode(body).encode()))

    def _request(self, body: bytes) -> urllib.request.Request:
        """Build a request to the Web API, with the session token."""
        request = urllib.request.Request(self._url, data=body)
        if self._token:
            request.add_header("X-SYNO-TOKEN", self._token)
        return request

    def _send(self, request: urllib.request.Request) -> dict[str, Any]:
        """Send a request; return the parsed JSON response."""
        with self._opener.open(request, timeout=600) as response:
            result: dict[str, Any] = json.load(response)
            return result

    @staticmethod
    def _data(response: dict[str, Any], call: str) -> dict[str, Any]:
        """Return the data of a response, or raise SynologyError."""
        if not response.get("success"):
            raise SynologyError(response.get("error", {}).get("code", 0), call)
        data: dict[str, Any] = response.get("data", {})
        return data
