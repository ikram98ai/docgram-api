

# ECR Repository
resource "aws_ecr_repository" "docgram_repo" {
  name                 = var.project
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = var.tags
}

# 🔧 Build & Push Docker Image
resource "null_resource" "build_and_push_image" {
  provisioner "local-exec" {
    command = <<EOT
      cd ..
      aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${aws_ecr_repository.docgram_repo.repository_url}
      docker build -t ${var.project} .
      docker tag ${var.project}:latest ${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}
      docker push ${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}
    EOT
  }
  triggers = {
    image_tag = var.image_tag
  }
  depends_on = [aws_ecr_repository.docgram_repo]
}

resource "aws_lambda_function" "docgram_lambda" {
  function_name = var.project
  role         = aws_iam_role.lambda_role.arn
  package_type = "Image"
  image_uri    = "${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}"
  timeout      = 30
  memory_size  = 512
  architectures = ["x86_64"]
  environment {
    variables = {
      GEMINI_API_KEY                = var.gemini_api_key
      PINECONE_API_KEY              = var.pinecone_api_key
      S3_BUCKET                     = aws_s3_bucket.docgram_storage.bucket
      STAGE                         = var.stage
      SECRET_KEY                    = var.secret_key
      ALGORITHM                     = "HS256"
      ACCESS_TOKEN_EXPIRE_MINUTES   = "30"
    }
  }
  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.docgram_lambda_logs,
    null_resource.build_and_push_image,
    aws_ecr_repository_policy.docgram_repo_policy,
  ]
  tags = var.tags
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "docgram_lambda_logs" {
  name              = "/aws/lambda/${var.project}"
  retention_in_days = 14
  tags              = var.tags
}