
############################################################# S3 BUCKET FOR STORING FILES #############################################################

resource "aws_s3_bucket" "docgram_storage" {
  bucket = "docgram-files"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "docgram_storage_public_access" {
  bucket                  = aws_s3_bucket.docgram_storage.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}


resource "aws_s3_bucket_website_configuration" "docgram_storage_website" {
  bucket = aws_s3_bucket.docgram_storage.id
  index_document {
    suffix = "index.html"
  }
  error_document {
    key = "error.html"
  }
}

resource "aws_s3_bucket_cors_configuration" "docgram_storage_cors" {
  bucket = aws_s3_bucket.docgram_storage.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}