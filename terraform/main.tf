terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  alias  = "us-east-1"
  region = "us-east-1"
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}


# ECR Repository
resource "aws_ecr_repository" "docgram_repo" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration {
    scan_on_push = true
  }
  tags = var.tags
}

# ECR Repository Policy
resource "aws_ecr_repository_policy" "docgram_repo_policy" {
  repository = aws_ecr_repository.docgram_repo.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPull"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
      }
    ]
  })
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "${var.function_name}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  tags = var.tags
}

# IAM Policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.function_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = aws_ecr_repository.docgram_repo.arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:*"
        ]
        Resource = [
          "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/khaneducation_*",
          "arn:aws:dynamodb:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/khaneducation_*/index/*"
        ]

      }
    ]
  })
}

# 🔧 Build & Push Docker Image
resource "null_resource" "build_and_push_image" {
  provisioner "local-exec" {
    command = <<EOT
      cd ..
      aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.docgram_repo.repository_url}
      docker build -t ${var.ecr_repository_name} .
      docker tag ${var.ecr_repository_name}:latest ${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}
      docker push ${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}
    EOT
  }
  triggers = {
    image_tag = var.image_tag
  }
  depends_on = [aws_ecr_repository.docgram_repo]
}

resource "aws_lambda_function" "docgram_lambda" {
  function_name = var.function_name
  role         = aws_iam_role.lambda_role.arn
  package_type = "Image"
  image_uri    = "${aws_ecr_repository.docgram_repo.repository_url}:${var.image_tag}"
  timeout      = 30
  memory_size  = 512
  architectures = ["x86_64"]
  environment {
    variables = {
      GEMINI_API_KEY                = var.gemini_api_key
      DEBUG                         = "False"
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
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = 14
  tags              = var.tags
}


############################################################# API GATEWAY CONFIGURATION #############################################################

# API Gateway (HTTP API)
resource "aws_apigatewayv2_api" "docgram_api" {
  name          = "${var.function_name}-api"
  protocol_type = "HTTP"
  tags          = var.tags
  cors_configuration {
    allow_credentials = false
    expose_headers    = ["*"]
    allow_headers     = ["*"]
    allow_methods     = ["*"]
    allow_origins     = ["*"]
    max_age          = 86400
  }
}

# API Gateway Integration with Lambda
resource "aws_apigatewayv2_integration" "docgram_integration" {
  api_id             = aws_apigatewayv2_api.docgram_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.docgram_lambda.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "proxy_route" {
  api_id    = aws_apigatewayv2_api.docgram_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.docgram_integration.id}"
}

# OPTIONS method for CORS preflight
resource "aws_apigatewayv2_route" "options_route" {
  api_id    = aws_apigatewayv2_api.docgram_api.id
  route_key = "OPTIONS /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.docgram_integration.id}"
}

# API Gateway Stage
resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.docgram_api.id
  name        = "$default"
  auto_deploy = true
}

# Lambda Permission for API Gateway
resource "aws_lambda_permission" "api_gw_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.docgram_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.docgram_api.execution_arn}/*/*"
}


############################################################# OUTPUTS #############################################################

# Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = aws_apigatewayv2_api.docgram_api.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.docgram_lambda.function_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.docgram_repo.repository_url
}