import asyncio
import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from app.config import get_settings
from app.errors import AppError, ServiceUnavailableError
from app.models.user import User

CODE_LIFETIME = timedelta(minutes=10)
RESEND_INTERVAL = timedelta(minutes=1)
MAX_ATTEMPTS = 5


def hash_code(email: str, code: str) -> str:
    return hmac.new(
        get_settings().jwt_secret.encode(),
        f"email-verification:{email}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()


def send_verification_email(email: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        raise ServiceUnavailableError(
            message="Отправка писем ещё не настроена", code="EMAIL_NOT_CONFIGURED"
        )
    message = EmailMessage()
    message["Subject"] = "Код подтверждения CashFlow Radar"
    message["From"] = settings.smtp_user
    message["To"] = email
    message.set_content(
        f"Код подтверждения: {code}\n\n"
        "Код действует 10 минут. Никому его не сообщайте.\n"
        "Если вы не регистрировались в CashFlow Radar, проигнорируйте письмо."
    )
    try:
        with smtplib.SMTP_SSL(
            settings.smtp_host,
            settings.smtp_port,
            context=ssl.create_default_context(),
            timeout=10,
        ) as smtp:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise ServiceUnavailableError(
            message="Не удалось отправить письмо. Попробуйте позже.",
            code="EMAIL_SEND_FAILED",
        ) from None


async def issue_code(user: User) -> None:
    now = datetime.now(UTC)
    if user.verification_sent_at and now - user.verification_sent_at < RESEND_INTERVAL:
        raise AppError(
            429, "EMAIL_RATE_LIMIT", "Повторная отправка доступна через минуту"
        )
    code = f"{secrets.randbelow(1_000_000):06d}"
    await asyncio.to_thread(send_verification_email, user.email, code)
    user.verification_code_hash = hash_code(user.email, code)
    user.verification_expires_at = datetime.now(UTC) + CODE_LIFETIME
    user.verification_sent_at = datetime.now(UTC)
    user.verification_attempts = 0
