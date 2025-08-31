import logging
from typing import Optional
from fastapi import (
    HTTPException,
)
import fitz, os
from ..utils import upload_to_s3

# Import our models
from ..models import (
    UserModel,
    PostModel
)
from dotenv import load_dotenv
from ..ai.rag import RAGIndexer
import os
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

gemini_base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
client = OpenAI( base_url=gemini_base_url, api_key=os.getenv("GEMINI_API_KEY"))
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

STAGE = os.getenv("STAGE", "dev")




def get_pdf_page_count(pdf_content: bytes) -> int:
    """Get page count from PDF bytes"""
    try:
        with fitz.Document(stream=pdf_content, filetype="pdf") as pdf_doc:
            return pdf_doc.page_count
    except Exception as e:
        logger.error(f"Error getting page count: {e}")
        return 1


def generate_pdf_thumbnail(pdf_content: bytes, post_id: str) -> Optional[str]:
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
                return upload_to_s3(img_data, thumbnail_key, "image/png")
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
async def process_pdf_embeddings(pdf_content: bytes, post_id: str):
    """Background task to process PDF for embeddings"""
    try:
        # This extract text and create embeddings for vector search
        logger.info(f"Processing PDF embeddings for post {post_id}")
        rag = RAGIndexer(pc, client)
        rag.create_index_if_not_exists()
        result = rag.upsert_pdf(pdf_content, post_id=post_id)

    except Exception as e:
        logger.error(f"PDF processing error for {post_id}: {e}")


async def ask_pdf_question(query: str, post_id: str, title: str) -> str:
    """Ask question to PDF using vector search"""
    try:
        # TODO: Implement your PDF question answering logic here
        # return ask_pdf(query, post_id, title)
        return "This is a placeholder response. Implement your PDF QA logic here."
    except Exception as e:
        logger.error(f"PDF QA error: {e}")
        return "Sorry, I'm having trouble processing your question right now."

