import json
import logging
import os

import boto3

COUNTER_ID = "count"
COUNTER_ATTRIBUTE = "visits"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _table():
    """Resolved per-invocation so tests can mock DynamoDB before first use."""
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _read_count():
    item = _table().get_item(Key={"id": COUNTER_ID}).get("Item")
    return int(item[COUNTER_ATTRIBUTE]) if item else 0


def _increment_count():
    """Atomic server-side increment; creates the item at 1 if absent."""
    result = _table().update_item(
        Key={"id": COUNTER_ID},
        UpdateExpression="ADD #attr :one",
        ExpressionAttributeNames={"#attr": COUNTER_ATTRIBUTE},
        ExpressionAttributeValues={":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(result["Attributes"][COUNTER_ATTRIBUTE])


def lambda_handler(event, context):
    method = event["requestContext"]["http"]["method"]

    try:
        if method == "GET":
            return _response(200, {"count": _read_count()})

        if method == "POST":
            return _response(200, {"count": _increment_count()})
    except Exception:
        # Detail goes to CloudWatch, never to the caller.
        logger.exception("visitor counter failed handling %s", method)
        return _response(500, {"error": "internal error"})

    return _response(405, {"error": "method not allowed"})
