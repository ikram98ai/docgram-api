from pydantic import BaseModel, Field, EmailStr, field_validator
from datetime import datetime
from typing import Optional, List


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None


# Pydantic Models for API responses


class User(BaseModel):
    id: str = Field(alias="user_id")
    username: str
    email: str
    full_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_following: Optional[bool] = None  # Context-dependent
    created_at: datetime

    @field_validator("full_name")
    def build_full_name(cls, v, values):
        if v:
            return v
        first = getattr(values, "first_name", None) or ""
        last = getattr(values, "last_name", None) or ""
        return f"{first} {last}".strip() if first or last else None

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class Post(BaseModel):
    id: str = Field(alias="post_id")
    user_id: str
    user: Optional[User] = None  # Nested user object
    title: str
    description: Optional[str] = None
    pdf_url: str
    thumbnail_url: Optional[str] = None
    file_size: int
    page_count: Optional[int] = None
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    is_liked: Optional[bool] = None  # Context-dependent
    created_at: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class Comment(BaseModel):
    id: str = Field(alias="comment_id")
    post_id: str
    user_id: str
    user: Optional[User] = None  # Nested user object
    content: str
    created_at: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class ChatConversation(BaseModel):
    id: str = Field(alias="conversation_id")
    post_id: str
    user_id: str
    messages: List["ChatMessage"] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class ChatMessage(BaseModel):
    id: str = Field(alias="message_id")
    conversation_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class FollowRelationship(BaseModel):
    id: str = Field(alias="relationship_id")
    follower_id: str
    following_id: str
    created_at: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class Like(BaseModel):
    id: str = Field(alias="like_id")
    post_id: str
    user_id: str
    created_at: datetime

    class Config:
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# Update forward references
ChatConversation.model_rebuild()

# Pydantic models for requests


class UserRegistrationRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: Optional[str] = Field(None, max_length=30)
    last_name: Optional[str] = Field(None, max_length=30)
    bio: Optional[str] = Field(None, max_length=500)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=30)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=30)
    last_name: Optional[str] = Field(None, max_length=30)
    bio: Optional[str] = Field(None, max_length=500)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class BookCreateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: bool = True


class BookUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class MessageRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, max_length=100)
