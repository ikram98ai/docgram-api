
############################################################# API GATEWAY CONFIGURATION #############################################################

# API Gateway (HTTP API)
resource "aws_apigatewayv2_api" "docgram_api" {
  name          = "${var.project}-api"
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