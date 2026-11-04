import asyncio
import smtplib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from app.config import get_settings
from app.email_verification import hash_code, send_verification_email
from app.errors import ServiceUnavailableError
from app.models.user import User
from app.security import create_access_token
from sqlalchemy import select

PAYLOAD = {
    "full_name": "Email verification",
    "email": "verification@example.com",
    "password": "Password123!",
}


@pytest.mark.asyncio
async def test_code_hash_attempt_limit_and_resend(client, mail_outbox, db_session):
    assert (await client.post("/api/auth/register", json=PAYLOAD)).status_code == 201
    email = PAYLOAD["email"]
    code = mail_outbox[email]
    user = await db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    assert not user.email_verified
    assert user.verification_code_hash == hash_code(email, code)
    assert user.verification_code_hash != code
    assert len(code) == 6 and code.isdigit()

    resend = {"email": email, "password": PAYLOAD["password"]}
    response = await client.post("/api/auth/resend-code", json=resend)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "EMAIL_RATE_LIMIT"
    assert (await client.post("/api/auth/register", json=PAYLOAD)).status_code == 429
    assert (
        await client.post("/api/auth/resend-code", json={**resend, "password": "wrong"})
    ).status_code == 401

    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        response = await client.post(
            "/api/auth/verify-email", json={"email": email, "code": wrong}
        )
        assert response.status_code == 400
    response = await client.post(
        "/api/auth/verify-email", json={"email": email, "code": code}
    )
    assert response.status_code == 429
    await db_session.refresh(user)
    assert user.verification_attempts == 5
    user.verification_sent_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()
    with patch("app.email_verification.secrets.randbelow", return_value=int(wrong)):
        assert (
            await client.post("/api/auth/resend-code", json=resend)
        ).status_code == 200
    assert mail_outbox[email] == wrong
    assert (
        await client.post("/api/auth/verify-email", json={"email": email, "code": code})
    ).status_code == 400
    assert (
        await client.post(
            "/api/auth/verify-email", json={"email": email, "code": wrong}
        )
    ).status_code == 200
    await db_session.refresh(user)
    assert user.email_verified
    assert user.verification_code_hash is None
    assert user.verification_expires_at is None
    assert user.verification_sent_at is None
    assert user.verification_attempts == 0
    assert (
        await client.post(
            "/api/auth/verify-email", json={"email": email, "code": wrong}
        )
    ).status_code == 400


@pytest.mark.asyncio
async def test_expired_code_and_validation(client, mail_outbox, db_session):
    await client.post("/api/auth/register", json=PAYLOAD)
    user = await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
    user.verification_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    response = await client.post(
        "/api/auth/verify-email",
        json={"email": user.email, "code": mail_outbox[user.email]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VERIFICATION_CODE_EXPIRED"
    for code in ("12", "abcdef", "１２３４５６", "1234567"):
        assert (
            await client.post(
                "/api/auth/verify-email", json={"email": user.email, "code": code}
            )
        ).status_code == 422
    for endpoint in ("verify-email", "resend-code"):
        data = (
            {"email": user.email, "code": "123456"}
            if endpoint == "verify-email"
            else {"email": user.email, "password": PAYLOAD["password"]}
        )
        response = await client.post(
            f"/api/auth/{endpoint}", json=data, headers={"Origin": "http://evil.com"}
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_unverified_token_is_blocked(client, db_session):
    await client.post("/api/auth/register", json=PAYLOAD)
    user = await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
    client.cookies.set("access_token", create_access_token(user.id, "csrf"))
    response = await client.get("/api/companies")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


@pytest.mark.asyncio
async def test_verification_is_one_time_under_concurrency(client, mail_outbox):
    await client.post("/api/auth/register", json=PAYLOAD)
    data = {"email": PAYLOAD["email"], "code": mail_outbox[PAYLOAD["email"]]}
    responses = await asyncio.gather(
        *(client.post("/api/auth/verify-email", json=data) for _ in range(2))
    )
    assert sorted(r.status_code for r in responses) == [200, 400]


@pytest.mark.asyncio
async def test_delivery_failure_does_not_create_account(
    client, db_session, monkeypatch
):
    def fail(_email, _code):
        raise ServiceUnavailableError(
            message="Письмо не отправлено", code="EMAIL_SEND_FAILED"
        )

    monkeypatch.setattr("app.email_verification.send_verification_email", fail)
    response = await client.post("/api/auth/register", json=PAYLOAD)
    assert response.status_code == 503
    assert not client.cookies
    assert (
        await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
        is None
    )


def test_smtp_ssl_and_sanitized_errors(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "smtp_user", "sender@mail.ru")
    from pydantic import SecretStr

    monkeypatch.setattr(settings, "smtp_password", SecretStr("app-password-for-test"))
    with patch("app.email_verification.smtplib.SMTP_SSL") as factory:
        smtp = factory.return_value.__enter__.return_value
        send_verification_email(PAYLOAD["email"], "012345")
        assert factory.call_args.args == ("smtp.mail.ru", 465)
        assert factory.call_args.kwargs["context"].check_hostname
        assert factory.call_args.kwargs["timeout"] == 10
        smtp.login.assert_called_once_with("sender@mail.ru", "app-password-for-test")
        message = smtp.send_message.call_args.args[0]
        assert message["From"] == "sender@mail.ru"
        assert message["To"] == PAYLOAD["email"]
        assert "012345" in message.get_content()
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"secret details")
        with pytest.raises(ServiceUnavailableError) as exc:
            send_verification_email(PAYLOAD["email"], "012345")
        assert exc.value.code == "EMAIL_SEND_FAILED"
        assert "secret" not in exc.value.message
    monkeypatch.setattr(settings, "smtp_password", SecretStr(""))
    with patch("app.email_verification.smtplib.SMTP_SSL", MagicMock()) as factory:
        with pytest.raises(ServiceUnavailableError) as exc:
            send_verification_email(PAYLOAD["email"], "012345")
        assert exc.value.code == "EMAIL_NOT_CONFIGURED"
        factory.assert_not_called()


@pytest.mark.asyncio
async def test_registration_can_recover_an_unverified_address(
    client, mail_outbox, db_session
):
    await client.post("/api/auth/register", json=PAYLOAD)
    old_code = mail_outbox[PAYLOAD["email"]]
    user = await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
    user.verification_sent_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()
    new_code = "000000" if old_code != "000000" else "111111"
    replacement = {
        **PAYLOAD,
        "password": "AnotherPassword123!",
        "full_name": "Recovered",
    }
    with patch("app.email_verification.secrets.randbelow", return_value=int(new_code)):
        response = await client.post("/api/auth/register", json=replacement)
    assert response.status_code == 201
    assert (
        await client.post(
            "/api/auth/verify-email", json={"email": user.email, "code": old_code}
        )
    ).status_code == 400
    assert (
        await client.post(
            "/api/auth/verify-email", json={"email": user.email, "code": new_code}
        )
    ).status_code == 200
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": PAYLOAD["password"]},
        )
    ).status_code == 401
    assert (
        await client.post(
            "/api/auth/login",
            json={"email": user.email, "password": replacement["password"]},
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_failed_resend_preserves_previous_code(
    client, mail_outbox, db_session, monkeypatch
):
    await client.post("/api/auth/register", json=PAYLOAD)
    code = mail_outbox[PAYLOAD["email"]]
    user = await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
    user.verification_sent_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()

    def fail(_email, _code):
        raise ServiceUnavailableError(
            message="Письмо не отправлено", code="EMAIL_SEND_FAILED"
        )

    monkeypatch.setattr("app.email_verification.send_verification_email", fail)
    response = await client.post(
        "/api/auth/resend-code",
        json={"email": user.email, "password": PAYLOAD["password"]},
    )
    assert response.status_code == 503
    assert (
        await client.post(
            "/api/auth/verify-email", json={"email": user.email, "code": code}
        )
    ).status_code == 200


@pytest.mark.asyncio
async def test_concurrent_resends_send_only_one_message(
    client, mail_outbox, db_session
):
    await client.post("/api/auth/register", json=PAYLOAD)
    user = await db_session.scalar(select(User).where(User.email == PAYLOAD["email"]))
    user.verification_sent_at = datetime.now(UTC) - timedelta(minutes=2)
    await db_session.commit()
    with patch("app.email_verification.send_verification_email") as send:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/api/auth/resend-code",
                    json={"email": user.email, "password": PAYLOAD["password"]},
                )
                for _ in range(2)
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 429]
    send.assert_called_once()
