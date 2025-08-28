import logging
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
from ..dependencies import get_current_user_id
from ..utils import upload_to_s3
from .utils import get_post_by_id, get_user_by_id, get_pdf_page_count, generate_pdf_thumbnail, process_pdf_embeddings, ask_pdf_question
# Import our models
from ..models import (
    UserModel,
    PostModel,
    LikeModel,
    CommentModel,
    ChatConversationModel,
    ChatMessageModel,
    FollowModel,
    get_current_user_context,
)
from ..schemas import (
    User,
    Post,
    BookUpdateRequest,
    ChatMessage,
    MessageRequest,
    Comment,
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/posts", tags=["Posts"])

# AWS clients (initialized once for Lambda container reuse)
STAGE = os.getenv("STAGE", "dev")

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
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
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
                    post_id=post.post_id,
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
                logger.warning(f"User {post.user_id} not found for post {post.post_id}")
                continue

        return result

    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{post_id}", response_model=Post)
async def get_post_detail(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Get post details"""
    try:
        post = await get_post_by_id(post_id)
        user = await get_user_by_id(post.user_id)

        # Get context
        context = get_current_user_context(current_user_id, post_id=post_id)

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
        ).dict()

        return Post(
            post_id=post.post_id,
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


@router.post("/", response_model=Post)
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

    if pdf_file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File size too large (max 50MB)")

    try:
        # Read PDF content
        pdf_content = await pdf_file.read()

        # Generate title if not provided
        if not title:
            filename = os.path.basename(pdf_file.filename)
            title = os.path.splitext(filename)[0].title()
        else:
            title = title.title()

        # Get page count
        page_count = get_pdf_page_count(pdf_content)

        # Generate post ID
        post_id = str(uuid.uuid4())

        # Upload PDF to S3
        pdf_key = f"{STAGE}/pdfs/{post_id}.pdf"
        pdf_url = upload_to_s3(pdf_content, pdf_key, "application/pdf")

        # Generate thumbnail
        thumbnail_url = await generate_pdf_thumbnail(pdf_content, post_id)

        # Create post in DynamoDB
        post = PostModel(
            post_id=post_id,
            user_id=current_user_id,
            title=title,
            description=description,
            pdf_url=pdf_url,
            thumbnail_url=thumbnail_url,
            file_size=len(pdf_content),
            page_count=page_count,
            is_public=int(is_public),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        post.save()

        # Update user's post count
        user = await get_user_by_id(current_user_id)
        user.posts_count += 1
        user.save()

        # Schedule background PDF processing
        background_tasks.add_task(process_pdf_embeddings, pdf_content, post_id, title)

        # Return created post
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
        ).dict()

        return Post(
            post_id=post.post_id,
            user_id=post.user_id,
            user=user_dict,
            title=post.title,
            description=post.description,
            pdf_url=post.pdf_url,
            thumbnail_url=post.thumbnail_url,
            file_size=post.file_size,
            page_count=post.page_count,
            likes_count=0,
            comments_count=0,
            shares_count=0,
            is_liked=False,
            created_at=post.created_at,
        )

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


@router.put("/{post_id}", response_model=Post)
async def update_post(
    post_id: str = Path(...),
    update_data: BookUpdateRequest = None,
    current_user_id: str = Depends(get_current_user_id),
):
    """Update a post"""
    try:
        post = await get_post_by_id(post_id)

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
        user = await get_user_by_id(post.user_id)
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
        ).dict()

        return Post(
            post_id=post.post_id,
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
        post = await get_post_by_id(post_id)

        # Check ownership
        if post.user_id != current_user_id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this post"
            )

        # Delete from S3 (optional - you might want to keep files for backup)
        # delete_from_s3(key=post.pdf_url.split('/')[-1])

        # Delete from DynamoDB
        post.delete()

        # Update user's post count
        user = await get_user_by_id(current_user_id)
        user.posts_count = max(0, user.posts_count - 1)
        user.save()

        return {"message": "Post deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{post_id}/like")
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


@router.get("/{post_id}/messages", response_model=List[ChatMessage])
async def get_post_messages(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Get chat messages for a post"""
    try:
        # Find or create conversation for this user and post
        conversation_id = f"{post_id}#{current_user_id}"

        try:
            conversation = ChatConversationModel.get(conversation_id)
        except ChatConversationModel.DoesNotExist:
            # Create new conversation
            conversation = ChatConversationModel(
                conversation_id=conversation_id,
                post_id=post_id,
                user_id=current_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            conversation.save()

        # Get messages
        messages = []
        for message in ChatMessageModel.conversation_messages_index.query(
            hash_key=conversation_id,
            scan_index_forward=True,  # Ascending order by timestamp
        ):
            messages.append(
                ChatMessage(
                    message_id=message.message_id,
                    conversation_id=message.conversation_id,
                    role=message.role,
                    content=message.content,
                    timestamp=message.timestamp,
                )
            )

        return messages

    except Exception as e:
        logger.error(f"Error getting messages for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{post_id}/messages", response_model=ChatMessage)
async def post_message(
    post_id: str = Path(...),
    message_request: MessageRequest = None,
    background_tasks: BackgroundTasks = None,
    current_user_id: str = Depends(get_current_user_id),
):
    """Post a message to chat with PDF"""
    try:
        # Find or create conversation
        conversation_id = f"{post_id}#{current_user_id}"

        try:
            conversation = ChatConversationModel.get(conversation_id)
        except ChatConversationModel.DoesNotExist:
            conversation = ChatConversationModel(
                conversation_id=conversation_id,
                post_id=post_id,
                user_id=current_user_id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            conversation.save()

        # Create user message
        user_message = ChatMessageModel(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=message_request.query,
            timestamp=datetime.now(timezone.utc),
        )
        user_message.save()

        # Create assistant message placeholder
        assistant_message = ChatMessageModel(
            message_id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content="Thinking...",
            timestamp=datetime.now(timezone.utc),
        )
        assistant_message.save()

        # Schedule response generation
        background_tasks.add_task(
            generate_assistant_response,
            assistant_message.message_id,
            message_request.query,
            post_id,
        )

        # Update conversation timestamp
        conversation.updated_at = datetime.now(timezone.utc)
        conversation.save()

        return ChatMessage(
            message_id=user_message.message_id,
            conversation_id=user_message.conversation_id,
            role=user_message.role,
            content=user_message.content,
            timestamp=user_message.timestamp,
        )

    except Exception as e:
        logger.error(f"Error posting message to {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def generate_assistant_response(message_id: str, query: str, post_id: str):
    """Background task to generate AI response"""
    try:
        # Get post info
        post = PostModel.get(post_id)

        # Generate response using your PDF QA system
        response = await ask_pdf_question(query, post_id, post.title)

        # Update assistant message
        message = ChatMessageModel.get(message_id)
        message.content = response
        message.timestamp = datetime.now(timezone.utc)
        message.save()

    except Exception as e:
        logger.error(f"Error generating response for message {message_id}: {e}")
        # Update with error message
        try:
            message = ChatMessageModel.get(message_id)
            message.content = (
                "Sorry, I'm having trouble processing your question right now."
            )
            message.save()
        except Exception as e:
            logger.error(
                f"Error generating response after 1st exeption for message {message_id}: {e}"
            )


@router.get("/search", response_model=List[Post])
async def search_posts(
    q: str = Query(..., min_length=1),
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    current_user_id: str = Depends(get_current_user_id),
):
    """Search posts by title"""
    try:
        # Note: DynamoDB doesn't have native text search
        # You might want to use OpenSearch/Elasticsearch for better search
        # For now, we'll do a scan with filter (not optimal for large datasets)

        posts = []
        for post in PostModel.scan(
            filter_condition=PostModel.title.contains(q.lower())
            & PostModel.is_public==1 
        ):
            posts.append(post)

        # Sort by creation date (newest first)
        posts.sort(key=lambda x: x.created_at, reverse=True)

        # Apply pagination
        paginated_posts = posts[offset : offset + limit]

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
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    bio=user.bio,
                    avatar_url=user.avatar_url,
                    followers_count=user.followers_count,
                    following_count=user.following_count,
                    posts_count=user.posts_count,
                    created_at=user.created_at,
                ).dict()

                post_dict = Post(
                    post_id=post.post_id,
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


@router.patch("/{post_id}/visibility")
async def toggle_post_visibility(
    post_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Toggle post public/private visibility"""
    try:
        post = await get_post_by_id(post_id)

        # Check ownership
        if post.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        post.is_public = int(not (post.is_public==1))
        post.updated_at = datetime.now(timezone.utc)
        post.save()

        return {"is_public": post.is_public==1}

    except Exception as e:
        logger.error(f"Error toggling visibility for post {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: str = Path(...), current_user_id: str = Depends(get_current_user_id)
):
    """Delete a chat message"""
    try:
        message = ChatMessageModel.get(message_id)

        # Check if user owns the conversation
        conversation = ChatConversationModel.get(message.conversation_id)
        if conversation.user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        message.delete()
        return {"message": "Message deleted successfully"}

    except ChatMessageModel.DoesNotExist:
        raise HTTPException(status_code=404, detail="Message not found")
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}")
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
                        full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
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
        post = await get_post_by_id(post_id)

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
        user = await get_user_by_id(current_user_id)
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
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    bio=user.bio,
                    avatar_url=user.avatar_url,
                    followers_count=user.followers_count,
                    following_count=user.following_count,
                    posts_count=user.posts_count,
                    created_at=user.created_at,
                ).dict()

                post_dict = Post(
                    post_id=post.post_id,
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
        logger.error(f"Error getting feed for user {current_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
