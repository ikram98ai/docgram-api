resource "aws_s3_bucket" "data_lake" {
  bucket        = "${var.project}-${data.aws_caller_identity.current.account_id}-${var.region}-datalake"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "scripts" {
  bucket        = "${var.project}-${data.aws_caller_identity.current.account_id}-${var.region}-scripts"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "scripts" {
  bucket = aws_s3_bucket.scripts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_object" "glue_extract_job_script" {
  bucket = aws_s3_bucket.scripts.id
  key    = "extract-job.py"
  source = "${path.root}/assets/glue_job/extract-job.py"

  etag = filemd5("${path.root}/assets/glue_job/extract-job.py")
}


resource "aws_s3_object" "glue_transform_job_script" {
  bucket = aws_s3_bucket.scripts.id
  key    = "transform-job.py"
  source = "${path.root}/assets/glue_job/transform-job.py"

  etag = filemd5("${path.root}/assets/glue_job/transform-job.py")
}
