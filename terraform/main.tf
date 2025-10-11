# terraform {
#   required_version = ">= 1.0"
#   required_providers {
#     aws = {
#       source  = "hashicorp/aws"
#       version = "~> 5.0"
#     }
#   }
# }


module "api" {
  source = "./modules/api"

  project             = var.project
  region              = var.region
  stage               = var.stage
  secret_key          = var.secret_key
  gemini_api_key      = var.gemini_api_key
  pinecone_api_key    = var.pinecone_api_key

}


# module "etl" {
#   source = "./modules/etl"

#   project             = var.project
#   region              = var.region
#   stage               = var.stage
# }
