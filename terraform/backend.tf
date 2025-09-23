# terraform/backend.tf
terraform {
  backend "s3" {
    bucket         = "terraform-state-20250610"
    key            = "docgram/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"      
  }
}


