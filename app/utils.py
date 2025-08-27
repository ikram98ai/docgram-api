import logging
import os
import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
from passlib.context import CryptContext
import re


# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


s3_client = boto3.client("s3")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "pdf-platform-files")
STAGE = os.getenv("STAGE", "dev")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def is_strong_password(password: str) -> bool:
    """Check password strength."""
    if (
        len(password) < 8
        or not re.search(r"[A-Z]", password)
        or not re.search(r"[a-z]", password)
        or not re.search(r"[0-9]", password)
        or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)
    ):
        return False
    return True


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def upload_to_s3(file_content: bytes, key: str, content_type: str) -> str:
    """Upload file to S3 and return URL"""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET, Key=key, Body=file_content, ContentType=content_type
        )
        return f"https://{S3_BUCKET}.s3.amazonaws.com/{key}"
    except ClientError as e:
        logger.error(f"S3 upload error: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")


def delete_from_s3(key: str):
    """Delete file from S3"""
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
    except ClientError as e:
        logger.error(f"S3 delete error: {e}")
        raise HTTPException(status_code=500, detail="File deletion failed")
