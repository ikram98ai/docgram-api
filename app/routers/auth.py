# app/routers/auth.py
from fastapi import APIRouter, status, HTTPException
from datetime import datetime, timezone
from typing import Optional
import uuid
from ..log_conf import logging
from ..schemas import User, TokenResponse, UserLoginRequest, UserRegistrationRequest
from ..models import UserModel
from ..dependencies import create_access_token
from ..utils import verify_password, hash_password

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


router = APIRouter(tags=["Authentication"])

# Security


async def authenticate_user(username: str, password: str) -> Optional[UserModel]:
    """Authenticate user by username/email and password"""
    try:
        # Try to find by username first
        try:
            user = next(UserModel.username_index.query(hash_key=username))
        except StopIteration:
            # Try to find by email
            try:
                user = next(UserModel.email_index.query(hash_key=username))
            except StopIteration:
                return None

        if not verify_password(password, user.password):
            return None

        return user
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None


@router.post("/login", response_model=TokenResponse)
async def login_user(login_data: UserLoginRequest):
    """Login user and return JWT token"""
    try:
        user = await authenticate_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
            )

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        user.save()

        # Create access token
        access_token = create_access_token(data={"sub": user.user_id})

        # Return token and user info
        user_dict = User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            bio=user.bio,
            avatar_url=user.avatar_url,
            followers_count=user.followers_count,
            following_count=user.following_count,
            posts_count=user.posts_count,
            created_at=user.created_at,
        )

        return TokenResponse(access_token=access_token, user=user_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/register/", response_model=TokenResponse)
async def register_user(user_data: UserRegistrationRequest):
    """Register a new user (SignupPageView equivalent)"""
    try:
        # Check if username already exists
        try:
            _ = next(UserModel.username_index.query(hash_key=user_data.username))
            raise HTTPException(status_code=400, detail="Username already registered")
        except StopIteration:
            pass

        # Check if email already exists
        try:
            _ = next(UserModel.email_index.query(hash_key=user_data.email))
            raise HTTPException(status_code=400, detail="Email already registered")
        except StopIteration:
            pass

        # Create new user
        user_id = str(uuid.uuid4())
        hashed_password = hash_password(user_data.password)

        user = UserModel(
            user_id=user_id,
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            bio=user_data.bio,
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        user.save()

        # Create access token
        access_token = create_access_token(data={"sub": user_id})

        # Return token and user info
        user_dict = User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
            bio=user.bio,
            avatar_url=user.avatar_url,
            followers_count=0,
            following_count=0,
            posts_count=0,
            created_at=user.created_at,
        )

        return TokenResponse(access_token=access_token, user=user_dict)

    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")
