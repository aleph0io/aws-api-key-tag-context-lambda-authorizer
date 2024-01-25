# This is a sample Python script.
import base64
import re
from os import getenv
import boto3

AWS_REGION = getenv("AWS_REGION")

PRINCIPAL_ID_TAG_NAME = getenv("PRINCIPAL_ID_TAG_NAME")

CONTEXT_TAG_PREFIX = getenv("CONTEXT_TAG_PREFIX", "context:")

DEFAULT_PRINCIPAL_ID = getenv("DEFAULT_PRINCIPAL_ID")

AUTHORIZATION_PLAN = getenv("AUTHORIZATION_PLAN", "authorization:bearer(plain)")

COPY_REQUEST_HEADERS = getenv("COPY_REQUEST_HEADERS", "")

api_gateway_client = None


def get_api_gateway_client():
    """ Retrieve AWS API Gateway Management client """

    global api_gateway_client

    if api_gateway_client is None:
        api_gateway_client = boto3.client("apigateway")

    return api_gateway_client


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


HEADER_AUTHORIZATION_PLAN_STEP = re.compile(r"header:([a-zA-Z0-9_-]+)[(][)]")

AUTHORIZATION_AUTHORIZATION_PLAN_STEP = re.compile(r"authorization:bearer[(](plain|base64)[)]")


def find_api_key(request):
    """ Extract bearer token if exists and is valid, or else None """

    authorization_plan_steps = AUTHORIZATION_PLAN.split(",")
    for authorization_plan_step in authorization_plan_steps:
        if AUTHORIZATION_AUTHORIZATION_PLAN_STEP.fullmatch(authorization_plan_step) is not None:
            match = AUTHORIZATION_AUTHORIZATION_PLAN_STEP.fullmatch(authorization_plan_step)
            instruction = match.group(1)
            authorization = find_first_header_value(request, "authorization")
            if authorization is not None:
                parts = authorization.split(" ", 1)
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]
                    if instruction == "base64":
                        token = base64.b64decode(token).decode("utf-8")
                    return token
        elif HEADER_AUTHORIZATION_PLAN_STEP.fullmatch(authorization_plan_step) is not None:
            match = HEADER_AUTHORIZATION_PLAN_STEP.fullmatch(authorization_plan_step)
            header_name = match.group(1)
            header_value = find_first_header_value(request, header_name)
            if header_value is not None:
                return header_value
        else:
            print("WARNING: Ignoring unrecognized authorization plan step: " + authorization_plan_step)


def fetch_api_key(value):
    pages = get_api_gateway_client().get_paginator("get_api_keys").paginate(
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

    # Grab our API key tags. The tags key only exists if tags are present, so be defensive.
    tags = api_key.get("tags", {})

    # Grab our principal ID from our tags
    principal_id = DEFAULT_PRINCIPAL_ID
    if PRINCIPAL_ID_TAG_NAME is not None:
        principal_id = tags.get(PRINCIPAL_ID_TAG_NAME, DEFAULT_PRINCIPAL_ID)
    if principal_id is None:
        raise Exception("Unauthorized")

    # What headers do we need to copy from the request to the context?
    copy_request_headers = COPY_REQUEST_HEADERS.split(",") if COPY_REQUEST_HEADERS != "" else []

    # Now compute our context from our tags
    context = {}
    context_prefix = CONTEXT_TAG_PREFIX
    context_prefix_len = len(context_prefix)
    for (k, v) in tags.items():
        if k.startswith(context_prefix):
            context[k[context_prefix_len:]] = v
    for header_name in copy_request_headers:
        header_value = find_first_header_value(request, header_name)
        if header_value is not None:
            context_name = header_name.replace("-", "_")
            context[context_name] = header_value

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
