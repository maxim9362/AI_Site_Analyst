from datetime import datetime, timedelta, timezone
import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.password_hash import (
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    validate_password_strength,
    verify_password,
)
from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserRead


class UserAlreadyExistsError(ValueError):
    pass


class PasswordPolicyError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("Password does not match security policy")
        self.errors = errors


class CurrentPasswordInvalidError(ValueError):
    pass


class PasswordResetTokenInvalidError(ValueError):
    pass


class UserService:
    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    def _validate_password(self, password: str, email: str) -> None:
        errors = validate_password_strength(password, email=email)
        if errors:
            raise PasswordPolicyError(errors)

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def register_user(self, data: UserCreate) -> UserRead:
        existing_user = await self.repository.get_by_email(data.email)
        if existing_user:
            raise UserAlreadyExistsError("User with this email already exists")

        self._validate_password(data.password, data.email)
        user = await self.repository.create_user(data.email, hash_password(data.password))
        return UserRead.model_validate(user)

    async def authenticate_user(self, email: str, password: str) -> UserRead | None:
        user = await self.repository.get_by_email(email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return UserRead.model_validate(user)

    async def get_or_create_google_user(self, email: str) -> tuple[UserRead, bool]:
        normalized_email = email.strip().lower()
        user = await self.repository.get_by_email(normalized_email)
        if user:
            return UserRead.model_validate(user), False

        random_password = secrets.token_urlsafe(48)
        user = await self.repository.create_user(normalized_email, hash_password(random_password))
        return UserRead.model_validate(user), True

    async def get_user_by_id(self, user_id):
        return await self.repository.get_by_id(user_id)

    async def create_password_reset_token(self, email: str) -> str | None:
        user = await self.repository.get_by_email(email)
        if not user or not user.is_active:
            return None

        now = datetime.now(timezone.utc)
        await self.repository.mark_user_reset_tokens_used(user.id, now)
        raw_token = generate_password_reset_token()
        await self.repository.create_password_reset_token(
            user.id,
            hash_password_reset_token(raw_token),
            now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES),
            now,
        )
        return raw_token

    async def reset_password(self, token: str, new_password: str) -> UserRead:
        reset_token = await self.repository.get_password_reset_token(hash_password_reset_token(token))
        now = datetime.now(timezone.utc)
        if (
            not reset_token
            or reset_token.used_at is not None
            or self._as_utc(reset_token.expires_at) <= now
        ):
            raise PasswordResetTokenInvalidError("Password reset token is invalid or expired")

        user = await self.repository.get_by_id(reset_token.user_id)
        if not user or not user.is_active:
            raise PasswordResetTokenInvalidError("Password reset token is invalid or expired")

        self._validate_password(new_password, user.email)
        await self.repository.update_password(user, hash_password(new_password), now)
        await self.repository.mark_user_reset_tokens_used(user.id, now)
        return UserRead.model_validate(user)

    async def change_password(self, user_id, current_password: str, new_password: str) -> UserRead:
        user = await self.repository.get_by_id(user_id)
        if not user or not user.is_active:
            raise CurrentPasswordInvalidError("Current password is invalid")
        if not verify_password(current_password, user.password_hash):
            raise CurrentPasswordInvalidError("Current password is invalid")

        self._validate_password(new_password, user.email)
        updated_user = await self.repository.update_password(
            user,
            hash_password(new_password),
            datetime.now(timezone.utc),
        )
        return UserRead.model_validate(updated_user)
