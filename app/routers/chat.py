from fastapi import APIRouter
import logging
import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import (
    HTTPException,
    Depends,
    Path,
)
from fastapi.responses import StreamingResponse
from ..dependencies import get_current_user_id
from .utils import get_post_by_id

# Import our models
from ..models import (
    ChatConversationModel,
    ChatMessageModel,
)
from ..schemas import (
    ChatMessage,
    MessageRequest,
)
from ..ai.ai_agents import agent_runner


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/posts", tags=["Messages"])


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

@router.post("/{post_id}/messages")
async def post_message(
    post_id: str = Path(...),
    message_request: MessageRequest = None,
    current_user_id: str = Depends(get_current_user_id),
):
    """Post a message to chat with PDF"""
    try:
        # Find or create conversation
        conversation_id = f"{post_id}#{current_user_id}"
        post = await get_post_by_id(post_id)
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

        query = (
            message_request.query
            + " in the PDF document titled: "
            + post.title
            + "\n Description: "
            + (post.description or "")
        )

        messages = [{"role": "user", "content": query}]

        async def response_generator():
            complete_response = ""
            async for chunk in agent_runner(messages, post_id=post_id):
                print("Chunk:", chunk)
                complete_response += chunk
                yield chunk
            
            # After streaming completes, save the assistant message
            conversation.updated_at = datetime.now(timezone.utc)
            conversation.save()

            assistant_message = ChatMessageModel(
                message_id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role="assistant",
                content=complete_response,
                timestamp=datetime.now(timezone.utc),
            )
            assistant_message.save()

        return StreamingResponse(response_generator(), media_type="text/plain")

    except Exception as e:
        logger.error(f"Error posting message to {post_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")