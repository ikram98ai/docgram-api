import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import (
    HTTPException,
    Depends,
    UploadFile,
    File,
    Form,
    Query,
    Path,
    BackgroundTasks,
    APIRouter,
)
from ..config import settings
from ..log_conf import logging
from ..dependencies import get_current_user_id
from ..utils import delete_from_s3
from .utils import (
    get_post_by_id,
    get_user_by_id,
    background_create_post,
    delete_embeddings,
    semantic_search,
)

# Import our models
from ..models import (
    UserModel,
    PostModel,
    CommentModel,
    FollowModel,
    get_current_user_context,
)
from ..schemas import (
    User,
    Post,
    BookUpdateRequest,
    Comment,
)


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/posts", tags=["Posts"])

# AWS clients (initialized once for Lambda container reuse)
STAGE = settings.stage


@router.get("/", response_model=List[Post])
async def list_posts(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    current_user_id: str = Depends(get_current_user_id),
):
    """List public posts with pagination"""
    try:
        posts = []
        # Query public posts using GSI
        for post in PostModel.public_posts_index.query(
            hash_key=1,
            scan_index_forward=False,  # Descending order
            limit=limit + offset,
        ):
            posts.append(post)

        # Apply offset (DynamoDB doesn't have native offset support)
        paginated_posts = posts[offset : offset + limit]

        # Convert to response format with user context
        result = []
        for post in paginated_posts:
            # Get user info
            try:
                user = UserModel.get(post.user_id)
                user_dict = User(
                    user_id=user.user_id,
                    username=user.username,
                    email=user.email,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}",
                    bio=user.bio,
                    avatar_url=user.avatar_url,
                    followers_count=user.followers_count,
                    following_count=user.following_count,
                    posts_count=user.posts_count,
                    created_at=user.created_at,
                ).dict()

                # Get context (is_liked)
                context = get_current_user_context(
                    current_user_id, post_id=post.post_id
                )

                post_dict = Post(
                    id=post.post_id,
                    user_id=post.user_id,
                    user=user_dict,
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
                    is_bookmarked=context.get("is_bookmarked", False),
                    created_at=post.created_at,
                    is_public=post.is_public == 1,
                ).dict()

                result.append(post_dict)

            except UserModel.DoesNotExist:
                logger.warning(f"User {post.user_id} not found for post {post.post_id}")
                continue

        return result

    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/feed", response_model=List[Post])
async def get_user_feed(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get personalized feed based on following"""
    try:
        # Get users that current user follows
        following_user_ids = set()
        for follow in FollowModel.follower_index.query(hash_key=current_user_id):
            following_user_ids.add(follow.following_id)

        # Add current user's posts
        following_user_ids.add(current_user_id)

        if not following_user_ids:
            # If not following anyone, return public posts
            return await list_posts(offset, limit, current_user_id)

        # Get posts from followed users
        all_posts = []
        for user_id in following_user_ids:
            try:
                for post in PostModel.user_posts_index.query(
                    hash_key=user_id,
                    scan_index_forward=False,
                    limit=50,  # Limit per user to prevent one user dominating feed
                ):
                    if post.is_public or post.user_id == current_user_id:
                        all_posts.append(post)
            except Exception as e:
                logger.warning(f"Error fetching posts for user {user_id}: {e}")
                continue

        # Sort by creation date
        all_posts.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        paginated_posts = all_posts[offset : offset + limit]

        # Convert to response format
        result = []
        for post in paginated_posts:
            try:
                user = UserModel.get(post.user_id)
                context = get_current_user_context(
                    current_user_id, post_id=post.post_id
                )

                user_dict = User(
                    user_id=user.user_id,
                    username=user.username,
                    email=user.email,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}",
                    bio=user.bio,
                    avatar_url=user.avatar_url,
                    followers_count=user.followers_count,
                    following_count=user.following_count,
                    posts_count=user.posts_count,
                    created_at=user.created_at,
                ).dict()

                post_dict = Post(
                    id=post.post_id,
                    user_id=post.user_id,
                    user=user_dict,
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
                    is_bookmarked=context.get("is_bookmarked", False),
                    created_at=post.created_at,
                ).dict()

                result.append(post_dict)

            except UserModel.DoesNotExist:
                continue

        return result

    except Exception as e:
        logger.error(f"Error getting feed for user {current_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search", response_model=List[Post])
async def search_posts(
    q: str = Query(..., min_length=1),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user_id: str = Depends(get_current_user_id),
):
    """Search posts by title"""
    try:
        # Note: DynamoDB doesn't have native text search
        # You might want to use OpenSearch/Elasticsearch for better search
        # For now, we'll do a scan with filter (not optimal for large datasets)

        post_ids = semantic_search(q)
        # Apply pagination
        paginated_post_ids = post_ids[offset : offset + limit]

        posts = PostModel.batch_get(paginated_post_ids)
        # Sort by creation date (newest first)
        # posts = sorted(posts, key=lambda x: x.created_at, reverse=True)

        # Convert to response format
        result = []
        for post in posts:
            try:
                user = UserModel.get(post.user_id)
                context = get_current_user_context(
                    current_user_id, post_id=post.post_id
                )

                user_dict = User(
                    user_id=user.user_id,
                    username=user.username,
                    email=user.email,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}",
                    bio=user.bio,
                    avatar_url=user.avatar_url,
                    followers_count=user.followers_count,
                    following_count=user.following_count,
                    posts_count=user.posts_count,
                    created_at=user.created_at,
                ).dict()

                post_dict = Post(
                    id=post.post_id,
                    user_id=post.user_id,
                    user=user_dict,
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
                ).dict()

                result.append(post_dict)

            except UserModel.DoesNotExist:
                continue

        return result

    except Exception as e:
        logger.error(f"Error searching posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/", response_model=dict)
async def create_post(
    background_tasks: BackgroundTasks,
    pdf_file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_public: bool = Form(True),
    current_user_id: str = Depends(get_current_user_id),
):
    """Create a new PDF post"""

    # Validate PDF file
    if not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if pdf_file.size > 10 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File size too large (max 10MB)")

    try:
        pdf_content = await pdf_file.read()

        # Generate title if not provided
        if not title:
            filename = os.path.basename(pdf_file.filename)
            title = os.path.splitext(filename)[0].title()
        else:
            title = title.title()

        background_tasks.add_task(
            background_create_post,
            pdf_content,
            title,
            is_public,
            description,
            current_user_id,
        )
        return {
            "message": "Post creation is in progress. You will be notified shortly."
        }
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


@router.get("/{post_id}", response_model=Post)
async def get_post_detail(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Get post details"""
    try:
        post = get_post_by_id(post_id)
        user = get_user_by_id(post.user_id)

        # Get context
        context = get_current_user_context(current_user_id, post_id=post_id)

        user_dict = User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=f"{user.first_name or ''} {user.last_name or ''}",
            bio=user.bio,
            avatar_url=user.avatar_url,
            followers_count=user.followers_count,
            following_count=user.following_count,
            posts_count=user.posts_count,
            created_at=user.created_at,
        ).dict()

        return Post(
            id=post.post_id,
            user_id=post.user_id,
            user=user_dict,
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
        )

    except Exception as e:
        logger.error(f"Error getting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{post_id}", response_model=Post)
async def update_post(
    post_id: str = Path(...),
    update_data: BookUpdateRequest = None,
    current_user_id: str = Depends(get_current_user_id),
):
    """Update a post"""
    try:
        post = get_post_by_id(post_id)

        # Check ownership
        if post.user_id != current_user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to update this post"
            )

        # Update fields
        if update_data.title:
            post.title = update_data.title.title()
        if update_data.description is not None:
            post.description = update_data.description
        if update_data.is_public is not None:
            post.is_public = int(update_data.is_public)

        post.updated_at = datetime.now(timezone.utc)
        post.save()

        # Get user info for response
        user = get_user_by_id(post.user_id)
        user_dict = User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=f"{user.first_name or ''} {user.last_name or ''}",
            bio=user.bio,
            avatar_url=user.avatar_url,
            followers_count=user.followers_count,
            following_count=user.following_count,
            posts_count=user.posts_count,
            created_at=user.created_at,
        ).dict()

        return Post(
            id=post.post_id,
            user_id=post.user_id,
            user=user_dict,
            title=post.title,
            description=post.description,
            pdf_url=post.pdf_url,
            thumbnail_url=post.thumbnail_url,
            file_size=post.file_size,
            page_count=post.page_count,
            likes_count=post.likes_count,
            comments_count=post.comments_count,
            shares_count=post.shares_count,
            is_liked=False,
            created_at=post.created_at,
        )

    except Exception as e:
        logger.error(f"Error updating post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{post_id}")
async def delete_post(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Delete a post"""
    try:
        post = get_post_by_id(post_id)

        # Check ownership
        if post.user_id != current_user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this post"
            )

        # Delete from S3 (optional - you might want to keep files for backup)
        delete_from_s3(key=post.pdf_url.split("/")[-1])

        # Delete from DynamoDB
        post.delete()
        delete_embeddings(post.post_id)
        # Update user's post count
        user = get_user_by_id(current_user_id)
        user.posts_count = max(0, user.posts_count - 1)
        user.save()

        return {"message": "Post deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{post_id}/comments", response_model=List[Comment])
async def get_post_comments(
    post_id: str = Path(...),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user_id: str = Depends(get_current_user_id),
):
    """Get comments for a post"""
    try:
        comments = []
        comment_count = 0

        for comment in CommentModel.post_comments_index.query(
            hash_key=post_id,
            scan_index_forward=True,  # Oldest first
            limit=limit + offset,
        ):
            if comment_count >= offset:
                try:
                    # Get user info for comment
                    user = UserModel.get(comment.user_id)
                    user_dict = User(
                        user_id=user.user_id,
                        username=user.username,
                        email=user.email,
                        full_name=f"{user.first_name or ''} {user.last_name or ''}",
                        bio=user.bio,
                        avatar_url=user.avatar_url,
                        followers_count=user.followers_count,
                        following_count=user.following_count,
                        posts_count=user.posts_count,
                        created_at=user.created_at,
                    ).dict()

                    comment_dict = Comment(
                        comment_id=comment.comment_id,
                        post_id=comment.post_id,
                        user_id=comment.user_id,
                        user=user_dict,
                        content=comment.content,
                        created_at=comment.created_at,
                    )

                    comments.append(comment_dict)

                except UserModel.DoesNotExist:
                    continue

            comment_count += 1
            if len(comments) >= limit:
                break

        return comments

    except Exception as e:
        logger.error(f"Error getting comments for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{post_id}/comments", response_model=Comment)
async def create_comment(
    post_id: str = Path(...),
    content: str = Form(..., min_length=1, max_length=1000),
    current_user_id: str = Depends(get_current_user_id),
):
    """Create a comment on a post"""
    try:
        # Verify post exists
        post = get_post_by_id(post_id)

        # Create comment
        comment = CommentModel(
            comment_id=str(uuid.uuid4()),
            post_id=post_id,
            user_id=current_user_id,
            content=content.strip(),
            created_at=datetime.now(timezone.utc),
        )
        comment.save()

        # Update post comment count
        post.comments_count += 1
        post.save()

        # Get user info for response
        user = get_user_by_id(current_user_id)
        user_dict = User(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=f"{user.first_name or ''} {user.last_name or ''}",
            bio=user.bio,
            avatar_url=user.avatar_url,
            followers_count=user.followers_count,
            following_count=user.following_count,
            posts_count=user.posts_count,
            created_at=user.created_at,
        ).dict()

        return Comment(
            comment_id=comment.comment_id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            user=user_dict,
            content=comment.content,
            created_at=comment.created_at,
        )

    except Exception as e:
        logger.error(f"Error creating comment on post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
