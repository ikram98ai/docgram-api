variable "project" {
  description = "Name of the Lambda function"
  type        = string
  default     = "docgram-app"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "stage" {
  description = "API Gateway stage name"
  type        = string
  default     = "prod"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
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

variable "pinecone_api_key" {
  description = "Pinecone API key"
  type        = string
  sensitive   = true
}


variable "secret_key" {
  description = "Secret key for JWT"
  type        = string
  sensitive   = true
}