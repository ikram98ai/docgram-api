include .env

sync:
	uv sync
lint:
	uv run ruff check

fix:
	uv run ruff check --fix

format:
	uv run ruff format

dev: 
	uv run fastapi run




# deploy:
# 	@echo "Deploying to AWS Lambda..."
# 	terraform -chdir=terraform init
# 	terraform -chdir=terraform plan -var="gemini_api_key=${GEMINI_API_KEY}" -var="secret_key=${SECRET_KEY}"
# 	terraform -chdir=terraform apply -var="gemini_api_key=${GEMINI_API_KEY}" -var="secret_key=${SECRET_KEY}"
destroy:
	@echo "Destroying AWS resources..."
	terraform -chdir=terraform destroy \
			  -var="gemini_api_key=${GEMINI_API_KEY}" \
			  -var="secret_key=${SECRET_KEY}" \
			  -lock=false

set-secrets:
	@echo "Setting GitHub Actions secrets..."
	gh secret set AWS_REGION --body ${AWS_REGION}
	gh secret set AWS_ACCESS_KEY_ID --body ${AWS_ACCESS_KEY_ID}
	gh secret set AWS_SECRET_ACCESS_KEY --body ${AWS_SECRET_ACCESS_KEY}
	gh secret set GEMINI_API_KEY --body ${GEMINI_API_KEY}
	gh secret set SECRET_KEY --body ${SECRET_KEY}
