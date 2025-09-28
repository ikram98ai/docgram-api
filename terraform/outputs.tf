# App Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = module.api.aws_apigatewayv2_api.docgram_api.api_endpoint
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.api.aws_lambda_function.docgram_lambda.function_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.api.aws_ecr_repository.docgram_repo.repository_url
}

# # ETL
# output "data_lake_bucket_id" {
#   value = module.etl.data_lake_bucket_id
# }

# output "scripts_bucket_id" {
#   value = module.etl.scripts_bucket_id
# }
