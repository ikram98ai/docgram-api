import logging
from typing import Optional, List, Set
from fastapi import  HTTPException, UploadFile
from datetime import datetime, timezone
from uuid import uuid4
import fitz
import os
import uuid
from ..utils import upload_to_s3

# Import our models
from ..models import UserModel, PostModel, ChatMessageModel, ChatConversationModel
from ..ai.rag import get_rag_instance
from ..ai.ai_agents import agent_runner

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STAGE = os.getenv("STAGE", "dev")


async def get_pdf_page_count(pdf_content: bytes) -> int:
    """Get page count from PDF bytes"""
    try:
        with fitz.Document(stream=pdf_content, filetype="pdf") as pdf_doc:
            return pdf_doc.page_count
    except Exception as e:
        logger.error(f"Error getting page count: {e}")
        return 1


async def generate_pdf_thumbnail(pdf_content: bytes, post_id: str) -> Optional[str]:
    """Generate thumbnail from first page of PDF"""
    try:
        with fitz.Document(stream=pdf_content, filetype="pdf") as pdf_doc:
            if pdf_doc.page_count > 0:
                first_page = pdf_doc[0]
                pixmap = first_page.get_pixmap(
                    matrix=fitz.Matrix(2.0, 2.0)
                )  # 2x scaling
                img_data = pixmap.tobytes("png")

                # Upload thumbnail to S3
                thumbnail_key = f"{STAGE}/thumbnails/{post_id}_thumbnail.png"
                return await upload_to_s3(img_data, thumbnail_key, "image/png")
    except Exception as e:
        logger.error(f"Thumbnail generation error: {e}")
    return None


async def get_user_by_id(user_id: str) -> UserModel:
    """Get user by ID with error handling"""
    try:
        return UserModel.get(user_id)
    except UserModel.DoesNotExist:
        raise HTTPException(status_code=404, detail="User not found")


async def get_post_by_id(post_id: str) -> PostModel:
    """Get post by ID with error handling"""
    try:
        return PostModel.get(post_id)
    except PostModel.DoesNotExist:
        raise HTTPException(status_code=404, detail="Post not found")


# Background task functions
async def process_pdf_embeddings(pdf_content: bytes, post_id: str, title: str):
    """Background task to process PDF for embeddings"""
    try:
        # This extract text and create embeddings for vector search
        logger.info(f"Processing PDF embeddings for post {post_id}")
        rag = get_rag_instance()
        rag.create_index_if_not_exists()
        result = await rag.upsert_pdf(pdf_content, title, post_id=post_id)
        return result
    except Exception as e:
        logger.error(f"PDF processing error for {post_id}: {e}")

async def delete_embeddings(post_id:str):
    rag = get_rag_instance()
    rag.delete_embeddings(post_id)


async def background_create_post(
    pdf_content: bytes,
    title: Optional[str],
    is_public: bool,
    description: Optional[str],
    current_user_id: str,
):
    """Background task to create a new PDF post"""
    try:
        # Generate unique post ID
        post_id = str(uuid.uuid4())

        # Upload PDF to S3
        pdf_key = f"{STAGE}/posts/{post_id}.pdf"
        pdf_url = await upload_to_s3(pdf_content, pdf_key, "application/pdf")

        # Get PDF metadata
        page_count = await get_pdf_page_count(pdf_content)
        file_size = len(pdf_content)

        # Generate thumbnail
        thumbnail_url = await generate_pdf_thumbnail(pdf_content, post_id)

        # Create post record in DynamoDB
        post = PostModel(
            post_id=post_id,
            user_id=current_user_id,
            title=title.title() if title else "Untitled",
            description=description or "",
            pdf_url=pdf_url,
            thumbnail_url=thumbnail_url or "",
            file_size=file_size,
            page_count=page_count,
            likes_count=0,
            comments_count=0,
            shares_count=0,
            is_public=1 if is_public else 0,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        post.save()

        # Update user's post count
        user = await get_user_by_id(current_user_id)
        user.posts_count += 1
        user.save()

        # Process PDF for embeddings in background
        await process_pdf_embeddings(pdf_content, post_id, post.title)

        logger.info(f"Post {post_id} created successfully")

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create post: {str(e)}")


async def response_generator(post_id:str, messages:List, conversation: ChatConversationModel):
    complete_response = ""
    async for chunk in agent_runner(messages, post_id=post_id):
        complete_response += chunk
        yield chunk

    # After streaming completes, save the assistant message
    conversation.updated_at = datetime.now(timezone.utc)
    conversation.save()

    assistant_message = ChatMessageModel(
        message_id=str(uuid4()),
        conversation_id=conversation.conversation_id,
        role="assistant",
        content=complete_response,
        timestamp=datetime.now(timezone.utc),
    )
    assistant_message.save()


async def semantic_search(query:str) -> List[str]:
    rag = get_rag_instance()
    res = rag.retrieval(query, top_k=50)

    post_ids = set()
    for c in res:
        meta = c.get("metadata", {})
        post_id = meta.get("post_id",None)
        print(f"Found {meta.get("source")} with score: {c.get("score")} post_id: {post_id}")
        if post_id and post_id not in post_ids:
            post_ids.add(post_id)
    return list(post_ids)