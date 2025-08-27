import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, Depends, UploadFile, File, Query, Path
from ..dependencies import get_current_user_id
from fastapi import APIRouter
import boto3

# Import our models
from ..models import UserModel, FollowModel, get_current_user_context
from ..schemas import User, UserUpdateRequest, Post
from ..models import PostModel
from ..utils import upload_to_s3

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/users", tags=["Users"])

# AWS clients (initialized once for Lambda container reuse)
STAGE = os.getenv("STAGE", "dev")


async def get_user_by_id(user_id: str) -> UserModel:
    """Get user by ID with error handling"""
    try:
        return UserModel.get(user_id)
    except UserModel.DoesNotExist:
        raise HTTPException(status_code=404, detail="User not found")


# Authentication Routes


@router.get("/me", response_model=User)
async def get_current_user_info(
    current_user_id: UserModel = Depends(get_current_user_id),
):
    """Get current user information"""
    current_user = await get_user_by_id(current_user_id)
    return User(
        user_id=current_user.user_id,
        username=current_user.username,
        email=current_user.email,
        full_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
        bio=current_user.bio,
        avatar_url=current_user.avatar_url,
        followers_count=current_user.followers_count,
        following_count=current_user.following_count,
        posts_count=current_user.posts_count,
        created_at=current_user.created_at,
    )


# User Profile Routes


@router.put("/profile", response_model=User)
async def update_user_profile(
    update_data: UserUpdateRequest = None,
    avatar_file: Optional[UploadFile] = File(None),
    current_user_id: UserModel = Depends(get_current_user_id),
):
    """Update user profile (ProfileUpdateView equivalent)"""
    try:
        current_user = await get_user_by_id(current_user_id)
        # Handle avatar upload if provided
        if avatar_file:
            if not avatar_file.filename.lower().endswith((".jpg", ".jpeg", ".png")):
                raise HTTPException(
                    status_code=400,
                    detail="Only JPG, JPEG, PNG files are allowed for avatar",
                )

            if avatar_file.size > 5 * 1024 * 1024:  # 5MB limit
                raise HTTPException(
                    status_code=400, detail="Avatar file size too large (max 5MB)"
                )

            # Upload avatar to S3
            avatar_content = await avatar_file.read()
            avatar_key = f"{STAGE}/avatars/{current_user.user_id}_{uuid.uuid4()}.jpg"
            avatar_url = await upload_to_s3(avatar_content, avatar_key, "image/jpeg")
            current_user.avatar_url = avatar_url

        # Update user fields
        if update_data:
            if update_data.username:
                # Check if username is already taken by another user
                try:
                    existing_user = next(
                        UserModel.username_index.query(hash_key=update_data.username)
                    )
                    if existing_user.user_id != current_user.user_id:
                        raise HTTPException(
                            status_code=400, detail="Username already taken"
                        )
                except StopIteration:
                    pass
                current_user.username = update_data.username

            if update_data.email:
                # Check if email is already taken by another user
                try:
                    existing_user = next(
                        UserModel.email_index.query(hash_key=update_data.email)
                    )
                    if existing_user.user_id != current_user.user_id:
                        raise HTTPException(
                            status_code=400, detail="Email already taken"
                        )
                except StopIteration:
                    pass
                current_user.email = update_data.email

            if update_data.first_name is not None:
                current_user.first_name = update_data.first_name
            if update_data.last_name is not None:
                current_user.last_name = update_data.last_name
            if update_data.bio is not None:
                current_user.bio = update_data.bio

        current_user.save()

        return User(
            user_id=current_user.user_id,
            username=current_user.username,
            email=current_user.email,
            full_name=f"{current_user.first_name or ''} {current_user.last_name or ''}".strip(),
            bio=current_user.bio,
            avatar_url=current_user.avatar_url,
            followers_count=current_user.followers_count,
            following_count=current_user.following_count,
            posts_count=current_user.posts_count,
            created_at=current_user.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")


@router.post("/{user_id}/follow")
async def follow_user(
    user_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Follow or unfollow a user (follow function equivalent)"""
    try:
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")

        # Check if target user exists
        target_user = await get_user_by_id(user_id)

        relationship_id = FollowModel.create_relationship_id(current_user_id, user_id)

        try:
            # Check if already following
            existing_follow = FollowModel.get(relationship_id)
            # Unfollow
            existing_follow.delete()
            current_user = await get_user_by_id(current_user_id)
            # Update counts
            current_user.following_count = max(0, current_user.following_count - 1)
            target_user.followers_count = max(0, target_user.followers_count - 1)

            is_following = False

        except FollowModel.DoesNotExist:
            # Follow
            follow = FollowModel(
                relationship_id=relationship_id,
                follower_id=current_user_id,
                following_id=user_id,
                created_at=datetime.now(timezone.utc),
            )
            follow.save()

            # Update counts
            current_user.following_count += 1
            target_user.followers_count += 1

            is_following = True

        # Save updated counts
        current_user.save()
        target_user.save()

        return {
            "following": is_following,  # Match your Django template variable name
            "followers_count": target_user.followers_count,
            "following_count": current_user.following_count,
        }

    except Exception as e:
        logger.error(f"Error following user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# @router.post("/{user_id}/follow")
# async def follow_user(
#     user_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
# ):
#     """Follow or unfollow a user"""
#     try:
#         if user_id == current_user_id:
#             raise HTTPException(status_code=400, detail="Cannot follow yourself")

#         # Check if target user exists
#         target_user = await get_user_by_id(user_id)
#         current_user = await get_user_by_id(current_user_id)

#         relationship_id = FollowModel.create_relationship_id(current_user_id, user_id)

#         try:
#             # Check if already following
#             existing_follow = FollowModel.get(relationship_id)
#             # Unfollow
#             existing_follow.delete()

#             # Update counts
#             current_user.following_count = max(0, current_user.following_count - 1)
#             target_user.followers_count = max(0, target_user.followers_count - 1)

#             is_following = False

#         except FollowModel.DoesNotExist:
#             # Follow
#             follow = FollowModel(
#                 relationship_id=relationship_id,
#                 follower_id=current_user_id,
#                 following_id=user_id,
#                 created_at=datetime.now(timezone.utc),
#             )
#             follow.save()

#             # Update counts
#             current_user.following_count += 1
#             target_user.followers_count += 1

#             is_following = True

#         # Save updated counts
#         current_user.save()
#         target_user.save()

#         return {
#             "is_following": is_following,
#             "followers_count": target_user.followers_count,
#             "following_count": current_user.following_count,
#         }

#     except Exception as e:
#         logger.error(f"Error following user {user_id}: {e}")
#         raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}/profile", response_model=Dict[str, Any])
async def get_user_profile(
    user_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Get user profile with posts and stats"""
    try:
        user = await get_user_by_id(user_id)

        # Get user's posts
        posts = []
        query_filter = None
        if user_id != current_user_id:
            # Show only public posts for other users
            query_filter = PostModel.is_public == True

        for post in PostModel.user_posts_index.query(
            hash_key=user_id,
            scan_index_forward=False,  # Newest first
            filter_condition=query_filter,
        ):
            context = get_current_user_context(current_user_id, post_id=post.post_id)

            post_dict = Post(
                post_id=post.post_id,
                user_id=post.user_id,
                title=post.title,
                description=post.description,
                pdf_url=post.pdf_url,
                thumbnail_url=post.thumbnail_url,
                file_size=post.file_size,
                page_count=post.page_count,
                likes_count=post.likes_count,
                comments_count=post.comments_count,
                shares_count=post.shares_count,
                is_liked=context.get("is_liked", False),
                created_at=post.created_at,
            ).model_dump()

            posts.append(post_dict)

        # Get follow context
        context = get_current_user_context(current_user_id, target_user_id=user_id)

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
            is_following=context.get("is_following", False),
            created_at=user.created_at,
        ).model_dump()

        return {
            "profile_user": user_dict,
            "posts": posts,
            "total_posts": len(posts),
            "total_followers": user.followers_count,
            "total_following": user.following_count,
        }

    except Exception as e:
        logger.error(f"Error getting profile for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}/followers", response_model=List[User])
async def get_user_followers(
    user_id: str = Path(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get user's followers"""
    try:
        followers = []
        count = 0

        for follow in FollowModel.following_index.query(
            hash_key=user_id,
            scan_index_forward=False,  # Newest first
            limit=limit + offset,
        ):
            if count >= offset:
                try:
                    user = UserModel.get(follow.follower_id)
                    context = get_current_user_context(
                        current_user_id, target_user_id=user.user_id
                    )

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
                        is_following=context.get("is_following", False),
                        created_at=user.created_at,
                    )

                    followers.append(user_dict)

                except UserModel.DoesNotExist:
                    continue

            count += 1
            if len(followers) >= limit:
                break

        return followers

    except Exception as e:
        logger.error(f"Error getting followers for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{user_id}/following", response_model=List[User])
async def get_user_following(
    user_id: str = Path(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get users that this user is following"""
    try:
        following = []
        count = 0

        for follow in FollowModel.follower_index.query(
            hash_key=user_id,
            scan_index_forward=False,  # Newest first
            limit=limit + offset,
        ):
            if count >= offset:
                try:
                    user = UserModel.get(follow.following_id)
                    context = get_current_user_context(
                        current_user_id, target_user_id=user.user_id
                    )

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
                        is_following=context.get("is_following", False),
                        created_at=user.created_at,
                    )

                    following.append(user_dict)

                except UserModel.DoesNotExist:
                    continue

            count += 1
            if len(following) >= limit:
                break

        return following

    except Exception as e:
        logger.error(f"Error getting following for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
