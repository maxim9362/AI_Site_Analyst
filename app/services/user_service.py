from sqlalchemy.ext.asyncio import AsyncSession

from app.core.password_hash import hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserRead


class UserAlreadyExistsError(ValueError):
    pass


class UserService:
    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)

    async def register_user(self, data: UserCreate) -> UserRead:
        existing_user = await self.repository.get_by_email(data.email)
        if existing_user:
            raise UserAlreadyExistsError("User with this email already exists")

        user = await self.repository.create_user(data.email, hash_password(data.password))
        return UserRead.model_validate(user)

    async def authenticate_user(self, email: str, password: str) -> UserRead | None:
        user = await self.repository.get_by_email(email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return UserRead.model_validate(user)
