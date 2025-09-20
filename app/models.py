from datetime import datetime
from typing import Dict, Any
from .config import settings
import uuid
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    UTCDateTimeAttribute,
    BooleanAttribute,
    NumberAttribute,
    JSONAttribute,
)
from pynamodb.indexes import AllProjection, GlobalSecondaryIndex
import os

# Environment configuration for DynamoDB
REGION = settings.aws_region
STAGE = settings.stage


class UserEmailIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "email-index"
        projection = AllProjection()  # More efficient for lookups

    email = UnicodeAttribute(hash_key=True)


class UsernameIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "username-index"
        projection = AllProjection()

    username = UnicodeAttribute(hash_key=True)


class UserModel(Model):
    """
    User model for DynamoDB
    """

    class Meta:
        table_name = f"docgram-{STAGE}-users"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"  # Serverless friendly

    # Primary Key
    user_id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))

    # Authentication
    username = UnicodeAttribute()
    email = UnicodeAttribute()
    password = UnicodeAttribute()  # Hashed password

    # User attributes
    first_name = UnicodeAttribute(null=True)
    last_name = UnicodeAttribute(null=True)
    bio = UnicodeAttribute(null=True)
    avatar_url = UnicodeAttribute(null=True)  # S3 URL

    # Social counts (denormalized for performance)
    followers_count = NumberAttribute(default=0)
    following_count = NumberAttribute(default=0)
    posts_count = NumberAttribute(default=0)

    # Status fields
    is_active = BooleanAttribute(default=True)
    is_superuser = BooleanAttribute(default=False)

    # Timestamps
    created_at = UTCDateTimeAttribute(default=datetime.now)
    last_login = UTCDateTimeAttribute(null=True)

    # GSI for email lookup
    email_index = UserEmailIndex()
    # GSI for username lookup
    username_index = UsernameIndex()


class FollowingIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "following-index"
        projection = AllProjection()  # More efficient for lookups

    following_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class FollowerIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "follower-index"
        projection = AllProjection()  # More efficient for lookups

    follower_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class FollowModel(Model):
    """
    Follow relationships model
    """

    class Meta:
        table_name = f"docgram-{STAGE}-follows"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Composite key: follower_id#following_id
    relationship_id = UnicodeAttribute(hash_key=True)  # follower_id#following_id
    follower_id = UnicodeAttribute()
    following_id = UnicodeAttribute()
    created_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for reverse lookups (who is following this user)
    following_index = FollowingIndex()

    # GSI for follower lookups (who is this user following)
    follower_index = FollowerIndex()

    @classmethod
    def create_relationship_id(cls, follower_id: str, following_id: str) -> str:
        return f"{follower_id}#{following_id}"


class UserPostIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "user-posts-index"
        projection = AllProjection()  # More efficient for lookups

    user_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class PublicPostIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "public-posts-index"
        projection = AllProjection()  # More efficient for lookups

    is_public = NumberAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class PostModel(Model):
    """
    PDF Post model for DynamoDB
    """

    class Meta:
        table_name = f"docgram-{STAGE}-posts"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Primary Key
    post_id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))

    # Post attributes
    user_id = UnicodeAttribute()
    title = UnicodeAttribute()
    description = UnicodeAttribute(null=True)
    slug = UnicodeAttribute(null=True)

    # File attributes
    pdf_url = UnicodeAttribute()  # S3 URL
    thumbnail_url = UnicodeAttribute(null=True)  # S3 URL for cover/thumbnail
    file_size = NumberAttribute()  # in bytes
    page_count = NumberAttribute(null=True)

    # Social metrics (denormalized for performance)
    likes_count = NumberAttribute(default=0)
    comments_count = NumberAttribute(default=0)
    shares_count = NumberAttribute(default=0)

    # Status
    is_public = NumberAttribute(default=1)

    # Timestamps
    created_at = UTCDateTimeAttribute(default=datetime.now)
    updated_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for user posts lookup
    user_posts_index = UserPostIndex()

    # GSI for public posts timeline
    public_posts_index = PublicPostIndex()


class UserLikeIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "user-likes-index"
        projection = AllProjection()  # More efficient for lookups

    user_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class PostLikeIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "post-likes-index"
        projection = AllProjection()  # More efficient for lookups

    post_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class LikeModel(Model):
    """
    Likes model for posts
    """

    class Meta:
        table_name = f"docgram-{STAGE}-likes"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Composite key: post_id#user_id
    like_id = UnicodeAttribute(hash_key=True)  # post_id#user_id
    post_id = UnicodeAttribute()
    user_id = UnicodeAttribute()
    created_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for user's likes lookup
    user_likes_index = UserLikeIndex

    # GSI for post's likes lookup
    post_likes_index = PostLikeIndex()

    @classmethod
    def create_like_id(cls, post_id: str, user_id: str) -> str:
        return f"{post_id}#{user_id}"


class PostCommentIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "post-comments-index"
        projection = AllProjection()  # More efficient for lookups

    post_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class CommentModel(Model):
    """
    Comments model for posts
    """

    class Meta:
        table_name = f"docgram-{STAGE}-comments"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Primary Key
    comment_id = UnicodeAttribute(
        hash_key=True, default_for_new=lambda: str(uuid.uuid4())
    )

    # Comment attributes
    post_id = UnicodeAttribute()
    user_id = UnicodeAttribute()
    content = UnicodeAttribute()
    created_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for post comments lookup
    post_comments_index = PostCommentIndex()


class UserConversationIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "user-conversations-index"
        projection = AllProjection()  # More efficient for lookups

    user_id = UnicodeAttribute(hash_key=True)
    updated_at = UTCDateTimeAttribute(range_key=True)


class PostConversationIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "post-conversations-index"
        projection = AllProjection()  # More efficient for lookups

    post_id = UnicodeAttribute(hash_key=True)
    updated_at = UTCDateTimeAttribute(range_key=True)


class ChatConversationModel(Model):
    """
    Chat conversations model for PDF interactions
    """

    class Meta:
        table_name = f"docgram-{STAGE}-chat-conversations"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Primary Key
    conversation_id = UnicodeAttribute(
        hash_key=True, default_for_new=lambda: str(uuid.uuid4())
    )

    # Conversation attributes
    post_id = UnicodeAttribute()
    user_id = UnicodeAttribute()
    title = UnicodeAttribute(null=True)  # Optional conversation title

    # Timestamps
    created_at = UTCDateTimeAttribute(default=datetime.now)
    updated_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for user conversations lookup
    user_conversations_index = UserConversationIndex()

    # GSI for PDF conversations lookup
    pdf_conversations_index = PostConversationIndex


class ConversationMessageIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "conversation-messages-index"
        projection = AllProjection()  # More efficient for lookups

    conversation_id = UnicodeAttribute(hash_key=True)
    timestamp = UTCDateTimeAttribute(range_key=True)


class ChatMessageModel(Model):
    """
    Chat messages model
    """

    class Meta:
        table_name = f"docgram-{STAGE}-chat-messages"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Primary Key
    message_id = UnicodeAttribute(
        hash_key=True, default_for_new=lambda: str(uuid.uuid4())
    )

    # Message attributes
    conversation_id = UnicodeAttribute()
    role = UnicodeAttribute()  # "user" or "assistant"
    content = UnicodeAttribute()
    timestamp = UTCDateTimeAttribute(default=datetime.now)

    # Metadata for AI responses
    metadata = JSONAttribute(null=True)  # For storing AI model info, tokens used, etc.

    # GSI for conversation messages lookup
    conversation_messages_index = ConversationMessageIndex()


class Notification(Model):
    class Meta:
        table_name = f"docgram-{STAGE}-notifications"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))

    user_id = UnicodeAttribute()
    title = UnicodeAttribute()
    message = UnicodeAttribute()
    notification_type = UnicodeAttribute()  # info, warning, success, error
    is_read = BooleanAttribute(default=False)
    action_url = UnicodeAttribute(null=True)
    expires_at = UTCDateTimeAttribute(null=True)


class UserBookmarkIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "user-bookmarks-index"
        projection = AllProjection()

    user_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class PostBookmarkIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "post-bookmarks-index"
        projection = AllProjection()

    post_id = UnicodeAttribute(hash_key=True)
    created_at = UTCDateTimeAttribute(range_key=True)


class BookmarkModel(Model):
    """
    Bookmarks model for posts
    """

    class Meta:
        table_name = f"docgram-{STAGE}-bookmarks"
        region = REGION
        billing_mode = "PAY_PER_REQUEST"

    # Composite key: post_id#user_id
    bookmark_id = UnicodeAttribute(hash_key=True)  # post_id#user_id
    post_id = UnicodeAttribute()
    user_id = UnicodeAttribute()
    created_at = UTCDateTimeAttribute(default=datetime.now)

    # GSI for user's bookmarks lookup
    user_bookmarks_index = UserBookmarkIndex()

    # GSI for post's bookmarks lookup
    post_bookmarks_index = PostBookmarkIndex()

    @classmethod
    def create_bookmark_id(cls, post_id: str, user_id: str) -> str:
        return f"{post_id}#{user_id}"


def get_current_user_context(
    user_id: str, target_user_id: str = None, post_id: str = None
) -> Dict[str, Any]:
    """
    Helper function to get context-dependent data (is_following, is_liked, is_bookmarked)
    Optimized for Lambda by batching queries when possible
    """
    context = {}

    if target_user_id and user_id != target_user_id:
        # Check if current user follows target user
        follow_id = FollowModel.create_relationship_id(user_id, target_user_id)
        try:
            FollowModel.get(follow_id)
            context["is_following"] = True
        except FollowModel.DoesNotExist:
            context["is_following"] = False

    if post_id:
        # Check if current user liked the post
        like_id = LikeModel.create_like_id(post_id, user_id)
        try:
            LikeModel.get(like_id)
            context["is_liked"] = True
        except LikeModel.DoesNotExist:
            context["is_liked"] = False

        # Check if current user bookmarked the post
        bookmark_id = BookmarkModel.create_bookmark_id(post_id, user_id)
        try:
            BookmarkModel.get(bookmark_id)
            context["is_bookmarked"] = True
        except BookmarkModel.DoesNotExist:
            context["is_bookmarked"] = False

    return context
