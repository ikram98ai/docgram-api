# App Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = module.api.api_gateway_url
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = module.api.lambda_function_name
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = module.api.ecr_repository_url
}

# # ETL
# output "data_lake_bucket_id" {
#   value = module.etl.data_lake_bucket_id
# }

# output "scripts_bucket_id" {
#   value = module.etl.scripts_bucket_id
# }
