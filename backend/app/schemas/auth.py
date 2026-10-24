from pydantic import BaseModel, Field, field_validator

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)  # 72 = bcrypt's byte limit

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserOut