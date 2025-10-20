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

output "docgram_s3_bucket" {
  description = "S3 bucket"
  value       = "https://${aws_s3_bucket.docgram_storage.bucket}.s3.${var.region}.amazonaws.com/"
}