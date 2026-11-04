"""Read verification codes from an explicitly configured test mailbox, never production."""

import json
import os
import urllib.parse
import urllib.request


def verification_code(email: str) -> str:
    url = os.environ.get("TEST_MAILBOX_URL")
    if not url:
        raise RuntimeError(
            "Email verification requires TEST_MAILBOX_URL pointing to a test-only mailbox. "
            "Do not run synthetic registrations against a real SMTP account."
        )
    request_url = f"{url}?{urllib.parse.urlencode({'email': email})}"
    with urllib.request.urlopen(request_url, timeout=5) as response:
        code = json.load(response)["code"]
    if (
        not isinstance(code, str)
        or len(code) != 6
        or not code.isascii()
        or not code.isdigit()
    ):
        raise RuntimeError("Test mailbox returned an invalid verification code")
    return code
