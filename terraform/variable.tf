variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
  default     = "docgram-app"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "docgram-app"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "prod"
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default = {
    Environment = "production"
    Project     = "docgram-app"
    ManagedBy   = "terraform"
  }
}

variable "gemini_api_key" {
  description = "Gemini API key"
  type        = string
  sensitive   = true
}


variable "secret_key" {
  description = "Secret key for JWT"
  type        = string
  sensitive   = true
}