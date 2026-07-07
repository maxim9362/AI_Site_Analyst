import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    pass


class EmailService:
    def _send(self, message: EmailMessage) -> None:
        if not settings.smtp_configured:
            raise EmailNotConfiguredError("SMTP settings are not configured")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME or settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)

    def send_password_reset_email(self, recipient: str, reset_link: str) -> None:
        message = EmailMessage()
        message["Subject"] = "Восстановление пароля AI Site Analyst"
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = recipient
        message.set_content(
            "\n".join(
                [
                    "Здравствуйте.",
                    "",
                    "Вы запросили восстановление пароля в AI Site Analyst.",
                    "Ссылка действует ограниченное время и может быть использована только один раз:",
                    reset_link,
                    "",
                    "Если вы не запрашивали восстановление, просто проигнорируйте это письмо.",
                ]
            )
        )
        try:
            self._send(message)
        except Exception:
            logger.exception("Failed to send password reset email")
            raise
