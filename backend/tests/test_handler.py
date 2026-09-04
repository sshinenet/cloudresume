import json

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "stevenshine-visitor-count"


@pytest.fixture
def table(monkeypatch):
    """A mocked DynamoDB table matching the one Terraform creates."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)

    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield dynamodb.Table(TABLE_NAME)


def request(method):
    """An API Gateway HTTP API (payload format 2.0) event."""
    return {"requestContext": {"http": {"method": method}}}


def test_get_on_empty_table_returns_zero(table):
    from handler import lambda_handler

    response = lambda_handler(request("GET"), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["count"] == 0


def test_post_on_empty_table_creates_counter_at_one(table):
    from handler import lambda_handler

    response = lambda_handler(request("POST"), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["count"] == 1


def test_unsupported_method_returns_405(table):
    from handler import lambda_handler

    response = lambda_handler(request("DELETE"), None)

    assert response["statusCode"] == 405


def test_post_increments_an_existing_count(table):
    from handler import lambda_handler

    table.put_item(Item={"id": "count", "visits": 41})

    response = lambda_handler(request("POST"), None)

    assert json.loads(response["body"])["count"] == 42


def test_get_does_not_change_the_count(table):
    from handler import lambda_handler

    table.put_item(Item={"id": "count", "visits": 7})

    lambda_handler(request("GET"), None)
    second = lambda_handler(request("GET"), None)

    assert json.loads(second["body"])["count"] == 7
    assert table.get_item(Key={"id": "count"})["Item"]["visits"] == 7


def test_dynamodb_failure_returns_500_instead_of_raising(table, monkeypatch):
    from handler import lambda_handler

    monkeypatch.setenv("TABLE_NAME", "table-that-does-not-exist")

    response = lambda_handler(request("GET"), None)

    assert response["statusCode"] == 500
