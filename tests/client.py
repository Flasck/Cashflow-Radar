"""
HTTP client for Cashflow Radar integration and acceptance tests.
Pure standard library implementation (urllib + http.cookiejar).
"""

import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


class APIResponse:
    """Represents an HTTP response from Cashflow Radar API."""

    def __init__(
        self,
        status_code: int,
        data: Any,
        raw_body: bytes,
        headers: dict[str, str],
        cookies: dict[str, str],
    ):
        self.status_code = status_code
        self.data = data
        self.raw_body = raw_body
        self.headers = headers
        self.cookies = cookies

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def error_code(self) -> str | None:
        """Extracts error.code if present in standard error envelope."""
        if isinstance(self.data, dict):
            err = self.data.get("error")
            if isinstance(err, dict):
                return err.get("code")
        return None

    @property
    def error_message(self) -> str | None:
        """Extracts error.message if present in standard error envelope."""
        if isinstance(self.data, dict):
            err = self.data.get("error")
            if isinstance(err, dict):
                return err.get("message")
        return None

    @property
    def safe_data(self) -> Any:
        """Returns data with credentials/tokens redacted for safe diagnostic printing."""
        if isinstance(self.data, dict):
            sensitive_keys = {
                "access_token",
                "token",
                "password",
                "password_hash",
                "csrf_token",
                "token_hash",
                "secret",
            }
            return {
                k: ("***" if k.lower() in sensitive_keys else v)
                for k, v in self.data.items()
            }
        return self.data

    def __repr__(self) -> str:
        return f"<APIResponse [{self.status_code}] code={self.error_code}>"


class TestAPIClient:
    """
    HTTP test client simulating browser interaction with Cashflow Radar backend:
    - Maintains cookie jar (access_token, csrf_token).
    - Sends Origin header (default: http://localhost:3000).
    - Sets X-CSRF-Token header matching csrf_token cookie on mutating requests.
    - Encodes JSON and multipart/form-data.
    """

    def __init__(
        self,
        base_url: str | None = None,
        origin: str | None = None,
        timeout: float = 15.0,
    ):
        self.base_url = (
            base_url or os.getenv("API_BASE_URL", "http://localhost:8000")
        ).rstrip("/")
        self.origin = origin or os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
        self.timeout = timeout
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.extra_headers: dict[str, str] = {}
        self.manual_cookies: dict[str, str] = {}

    def new_session(self) -> "TestAPIClient":
        """Spawns a clean client instance with identical base_url and origin."""
        return TestAPIClient(
            base_url=self.base_url,
            origin=self.origin,
            timeout=self.timeout,
        )

    def get_cookie(self, name: str) -> str | None:
        """Retrieves cookie value from jar or manual cookies."""
        for cookie in self.cookie_jar:
            if cookie.name == name:
                return cookie.value
        return self.manual_cookies.get(name)

    @property
    def csrf_token(self) -> str | None:
        return self.get_cookie("csrf_token")

    @property
    def access_token(self) -> str | None:
        return self.get_cookie("access_token")

    def _encode_multipart(
        self,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
    ) -> tuple[bytes, str]:
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()

        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
            )
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        for key, (filename, file_bytes, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
            body.extend(file_bytes)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode())
        return bytes(body), f"multipart/form-data; boundary={boundary}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: Any | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        omit_origin: bool = False,
        omit_csrf: bool = False,
        custom_csrf: str | None = None,
        custom_origin: str | None = None,
    ) -> APIResponse:
        url = (
            path
            if path.startswith(("http://", "https://"))
            else f"{self.base_url}{path}"
        )
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            url = f"{url}?{query}"

        req_headers: dict[str, str] = {
            "Accept": "application/json",
            **self.extra_headers,
        }

        # Origin header for browser consistency
        if not omit_origin:
            req_headers["Origin"] = custom_origin or self.origin

        # CSRF token header on mutating requests
        method_upper = method.upper()
        if method_upper in ("POST", "PATCH", "PUT", "DELETE") and not omit_csrf:
            csrf_val = custom_csrf or self.csrf_token
            if csrf_val:
                req_headers["X-CSRF-Token"] = csrf_val

        body_bytes: bytes | None = None

        if files:
            fields = json_data if isinstance(json_data, dict) else {}
            body_bytes, content_type = self._encode_multipart(fields, files)
            req_headers["Content-Type"] = content_type
        elif json_data is not None:
            body_bytes = json.dumps(json_data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif data is not None:
            body_bytes = data

        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(
            url=url,
            data=body_bytes,
            headers=req_headers,
            method=method_upper,
        )

        status_code = 0
        raw_body = b""
        resp_headers: dict[str, str] = {}
        resp_cookies: dict[str, str] = {}

        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                status_code = resp.status
                raw_body = resp.read()
                resp_headers = dict(resp.headers)
        except urllib.error.HTTPError as e:
            status_code = e.code
            raw_body = e.read()
            resp_headers = dict(e.headers)
        except urllib.error.URLError as e:
            # Server unreachable or connection error
            return APIResponse(
                status_code=503,
                data={
                    "error": {
                        "code": "CONNECTION_FAILED",
                        "message": str(e.reason),
                    }
                },
                raw_body=str(e.reason).encode("utf-8"),
                headers={},
                cookies={},
            )

        # Collect cookies from jar
        for c in self.cookie_jar:
            resp_cookies[c.name] = c.value

        # In case server sent Set-Cookie manually
        set_cookie_headers = [
            v for k, v in resp_headers.items() if k.lower() == "set-cookie"
        ]
        for sc in set_cookie_headers:
            parts = sc.split(";", 1)[0].split("=", 1)
            if len(parts) == 2:
                self.manual_cookies[parts[0].strip()] = parts[1].strip()
                resp_cookies[parts[0].strip()] = parts[1].strip()

        parsed_data = None
        if raw_body:
            try:
                parsed_data = json.loads(raw_body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                parsed_data = raw_body.decode("utf-8", errors="replace")

        return APIResponse(
            status_code=status_code,
            data=parsed_data,
            raw_body=raw_body,
            headers=resp_headers,
            cookies=resp_cookies,
        )

    # Convenience HTTP verbs
    def get(
        self, path: str, params: dict[str, Any] | None = None, **kwargs
    ) -> APIResponse:
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path: str, json_data: Any | None = None, **kwargs) -> APIResponse:
        return self.request("POST", path, json_data=json_data, **kwargs)

    def patch(self, path: str, json_data: Any | None = None, **kwargs) -> APIResponse:
        return self.request("PATCH", path, json_data=json_data, **kwargs)

    def delete(self, path: str, **kwargs) -> APIResponse:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        """Clear cookies and close active sessions."""
        self.cookie_jar.clear()
        self.manual_cookies.clear()
