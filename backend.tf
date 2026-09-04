# Visitor counter backend: DynamoDB + Lambda behind an API Gateway HTTP API.
# Resource names must keep the "stevenshine-" prefix; the deploy credential is
# scoped to it.

resource "aws_dynamodb_table" "visitor_count" {
  name         = "stevenshine-visitor-count"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

data "aws_iam_policy_document" "visitor_counter_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "visitor_counter" {
  name               = "stevenshine-visitor-counter-role"
  assume_role_policy = data.aws_iam_policy_document.visitor_counter_assume_role.json
}

data "aws_iam_policy_document" "visitor_counter" {
  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.visitor_count.arn]
  }

  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

resource "aws_iam_role_policy" "visitor_counter" {
  name   = "stevenshine-visitor-counter-policy"
  role   = aws_iam_role.visitor_counter.id
  policy = data.aws_iam_policy_document.visitor_counter.json
}

data "archive_file" "visitor_counter" {
  type        = "zip"
  source_file = "${path.module}/backend/handler.py"
  output_path = "${path.module}/backend/handler.zip"
}

resource "aws_lambda_function" "visitor_counter" {
  function_name    = "stevenshine-visitor-counter"
  role             = aws_iam_role.visitor_counter.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.visitor_counter.output_path
  source_code_hash = data.archive_file.visitor_counter.output_base64sha256

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.visitor_count.name
    }
  }
}

resource "aws_apigatewayv2_api" "visitor_counter" {
  name          = "stevenshine-visitor-counter-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://${var.domain_name_simple}", "https://www.${var.domain_name_simple}"]
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_integration" "visitor_counter" {
  api_id                 = aws_apigatewayv2_api.visitor_counter.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.visitor_counter.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "get_count" {
  api_id    = aws_apigatewayv2_api.visitor_counter.id
  route_key = "GET /count"
  target    = "integrations/${aws_apigatewayv2_integration.visitor_counter.id}"
}

resource "aws_apigatewayv2_route" "post_count" {
  api_id    = aws_apigatewayv2_api.visitor_counter.id
  route_key = "POST /count"
  target    = "integrations/${aws_apigatewayv2_integration.visitor_counter.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.visitor_counter.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.visitor_counter.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.visitor_counter.execution_arn}/*/*"
}

output "visitor_counter_api" {
  value = aws_apigatewayv2_stage.default.invoke_url
}
