# This is a sample Python script.
from os import getenv
import boto3

api_gateway_client = boto3.client("apigateway")

AWS_REGION = getenv("AWS_REGION")

PRINCIPAL_ID_TAG_NAME = getenv("PRINCIPAL_ID_TAG_NAME")

CONTEXT_TAG_PREFIX = getenv("CONTEXT_TAG_PREFIX", "context:")

DEFAULT_PRINCIPAL_ID = getenv("DEFAULT_PRINCIPAL_ID")


def find_first_header_value(request, header_name):
    """ Returns the first value of the given header if it exists, or else None """

    # We want our header names to be case-insensitive
    header_name = header_name.lower()

    # Find the header value case-insensitively
    values = [v for (k, v) in request["headers"].items() if k.lower() == header_name]
    if len(values) == 0:
        return None

    # Values are comma-separated, so only take the first one
    value = values[0]
    if "," in value:
        index = value.index(",")
        value = value[0:index]

    return value


def find_api_key(request):
    """ Extract bearer token if exists and is valid, or else None """

    authorization = find_first_header_value(request, "authorization")
    if authorization is None:
        return None

    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        return None
    if parts[0].lower() != "bearer":
        return None

    return parts[1]


def fetch_api_key(value):
    pages = api_gateway_client.get_paginator("get_api_keys").paginate(
        includeValues=True,
        PaginationConfig={
            'PageSize': 500
        })
    for page in pages:
        for item in page["items"]:
            if item["value"] == value:
                return item
    return None


# https://github.com/amazon-archives/serverless-app-examples/tree/master/python/api-gateway-authorizer-python
# https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-input.html#w38aac15b9c11c26c29b5
def lambda_handler(request, context):
    # Get the API key value
    # TODO Implement other schemes for extracting API key from request
    api_key_value = find_api_key(request)
    if api_key_value is None:
        raise Exception("Unauthorized")

    # TODO Implement other schemes for looking up API key from API Gateway API
    api_key = fetch_api_key(api_key_value)
    if api_key is None:
        raise Exception("Unauthorized")

    # Let's extract some important facts about this API request
    request_context = request["requestContext"]
    api_aws_account_id = request_context["accountId"]
    api_id = request_context["apiId"]
    api_stage = request_context["stage"]

    # Grab our API key tags
    tags = api_key["tags"]

    # Grab our principal ID from our tags
    principal_id = DEFAULT_PRINCIPAL_ID
    if PRINCIPAL_ID_TAG_NAME is not None:
        principal_id = tags.get(PRINCIPAL_ID_TAG_NAME, DEFAULT_PRINCIPAL_ID)
    if principal_id is None:
        raise Exception("Unauthorized")

    # Now compute our context from our tags
    context = {}
    context_prefix = CONTEXT_TAG_PREFIX
    context_prefix_len = len(context_prefix)
    for (k, v) in tags.items():
        if k.startswith(context_prefix):
            context[k[context_prefix_len:]] = v

    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": f"arn:aws:execute-api:{AWS_REGION}:{api_aws_account_id}:{api_id}/{api_stage}/*"
                }
            ]
        },
        "context": context,
        "usageIdentifierKey": api_key_value
    }
