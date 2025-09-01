from fastapi import APIRouter
import logging
from datetime import datetime, timezone
from fastapi import (
    HTTPException,
    Depends,
    Path,
)
from ..dependencies import get_current_user_id
from .utils import get_post_by_id, get_user_by_id

# Import our models
from ..models import LikeModel, BookmarkModel, FollowModel


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

post_router = APIRouter(prefix="/posts", tags=["Toggles"])

user_router = APIRouter(prefix="/users", tags=["Toggles"])


@user_router.post("/{user_id}/follow")
async def toggle_follow(
    user_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Follow or unfollow a user (follow function equivalent)"""
    try:
        if user_id == current_user_id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")

        # Check if target user exists
        target_user = await get_user_by_id(user_id)
        current_user = await get_user_by_id(current_user_id)

        relationship_id = FollowModel.create_relationship_id(current_user_id, user_id)

        try:
            # Check if already following
            existing_follow = FollowModel.get(relationship_id)
            # Unfollow
            existing_follow.delete()
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


@post_router.post("/{post_id}/like")
async def toggle_like(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Toggle like on a post"""
    try:
        post = await get_post_by_id(post_id)
        like_id = LikeModel.create_like_id(post_id, current_user_id)

        try:
            # Check if already liked
            existing_like = LikeModel.get(like_id)
            # Unlike
            existing_like.delete()
            post.likes_count = max(0, post.likes_count - 1)
            is_liked = False
        except LikeModel.DoesNotExist:
            # Like
            like = LikeModel(
                like_id=like_id,
                post_id=post_id,
                user_id=current_user_id,
                created_at=datetime.now(timezone.utc),
            )
            like.save()
            post.likes_count += 1
            is_liked = True

        post.save()

        return {"is_liked": is_liked, "likes_count": post.likes_count}

    except Exception as e:
        logger.error(f"Error toggling like for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@post_router.post("/{post_id}/bookmark")
async def toggle_bookmark(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Toggle bookmark on a post"""
    try:
        _ = await get_post_by_id(post_id)
        bookmark_id = BookmarkModel.create_bookmark_id(post_id, current_user_id)

        try:
            # Check if already bookmarked
            existing_bookmark = BookmarkModel.get(bookmark_id)
            # Unbookmark
            existing_bookmark.delete()
            is_bookmarked = False
        except BookmarkModel.DoesNotExist:
            # Bookmark
            bookmark = BookmarkModel(
                bookmark_id=bookmark_id,
                post_id=post_id,
                user_id=current_user_id,
                created_at=datetime.now(timezone.utc),
            )
            bookmark.save()
            is_bookmarked = True

        return {"is_bookmarked": is_bookmarked}

    except Exception as e:
        logger.error(f"Error toggling bookmark for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@post_router.patch("/{post_id}/visibility")
async def toggle_post_visibility(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Toggle post public/private visibility"""
    try:
        post = await get_post_by_id(post_id)

        # Check ownership
        if post.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        post.is_public = int(not (post.is_public == 1))
        post.updated_at = datetime.now(timezone.utc)
        post.save()

        return {"is_public": post.is_public == 1}

    except Exception as e:
        logger.error(f"Error toggling visibility for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
