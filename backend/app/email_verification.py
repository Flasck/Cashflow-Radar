import asyncio
import hashlib
import hmac
import math
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from html import escape

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


def send_verification_email(
    email: str, code: str, *, password_change: bool = False
) -> None:
    message = EmailMessage()
    title = "Подтвердите смену пароля" if password_change else "Подтвердите почту"
    instruction = (
        "Введите этот код в настройках аккаунта, чтобы изменить пароль."
        if password_change
        else "Введите этот код на странице регистрации, чтобы завершить создание аккаунта."
    )
    footer = (
        "Если вы не запрашивали смену пароля, не сообщайте код и проверьте безопасность аккаунта."
        if password_change
        else "Если вы не регистрировались в CashFlow Radar, просто проигнорируйте письмо."
    )
    message["Subject"] = f"{title} — CashFlow Radar"
    message["To"] = email
    message.set_content(
        f"Код подтверждения: {code}\n\n"
        f"{instruction}\n\n"
        "Код действует 10 минут. Никому его не сообщайте.\n"
        f"{footer}"
    )
    message.add_alternative(
        f"""<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f7f5f2;color:#292522;font-family:Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
    <tr><td align="center" style="padding:32px 16px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
        style="max-width:480px;background:#ffffff;border:1px solid #e1dcd6;border-radius:8px;">
        <tr><td style="padding:28px 28px 20px;border-bottom:3px solid #b74632;">
          <span style="font-size:18px;font-weight:bold;">CashFlow Radar</span>
        </td></tr>
        <tr><td style="padding:28px;">
          <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;">{title}</h1>
          <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">
            {instruction}
          </p>
          <div style="padding:20px 12px;background:#f7f5f2;border:1px solid #e1dcd6;
            border-radius:6px;text-align:center;font-size:36px;font-weight:bold;
            letter-spacing:8px;color:#292522;">{escape(code)}</div>
          <p style="margin:20px 0 0;font-size:14px;line-height:1.6;color:#71665e;">
            Код действует <strong>10 минут</strong>. Никому его не сообщайте.
          </p>
        </td></tr>
        <tr><td style="padding:20px 28px;border-top:1px solid #e1dcd6;
          font-size:13px;line-height:1.6;color:#71665e;">
          {footer}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""",
        subtype="html",
    )
    send_email(message)


def send_invitation_email(email: str, company_name: str) -> None:
    url = f"{get_settings().allowed_origins[0].rstrip('/')}/invitations"
    message = EmailMessage()
    message["Subject"] = "Вас пригласили в компанию — CashFlow Radar"
    message["To"] = email
    message.set_content(
        f"Вас ждут в компании «{company_name}» на CashFlow Radar.\n\n"
        f"Откройте сайт: {url}\n"
        "Войдите или зарегистрируйтесь с этим адресом электронной почты и "
        "подтвердите её. Приглашение находится в разделе «Приглашения».\n\n"
        "Приглашение действует 48 часов. Если оно вам неизвестно, "
        "просто проигнорируйте это письмо."
    )
    send_email(message)


def send_email(message: EmailMessage) -> None:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password.get_secret_value():
        raise ServiceUnavailableError(
            message="Отправка писем ещё не настроена", code="EMAIL_NOT_CONFIGURED"
        )
    message["From"] = settings.smtp_user
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


def retry_after(user: User) -> int:
    if user.verification_sent_at is None:
        return 0
    remaining = user.verification_sent_at + RESEND_INTERVAL - datetime.now(UTC)
    return max(0, math.ceil(remaining.total_seconds()))


async def issue_code(user: User) -> None:
    remaining = retry_after(user)
    if remaining:
        raise AppError(
            429,
            "EMAIL_RATE_LIMIT",
            "Повторная отправка пока недоступна",
            fields={"retry_after": str(remaining)},
        )
    code = f"{secrets.randbelow(1_000_000):06d}"
    await asyncio.to_thread(send_verification_email, user.email, code)
    user.verification_code_hash = hash_code(user.email, code)
    user.verification_expires_at = datetime.now(UTC) + CODE_LIFETIME
    user.verification_sent_at = datetime.now(UTC)
    user.verification_attempts = 0
