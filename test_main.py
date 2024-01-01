import pytest

from unittest.mock import patch, MagicMock

from main import find_first_header_value
from main import find_api_key
from main import fetch_api_key
from main import lambda_handler


# lambda_handler
def test_lambda_handler_api_key_missing():
    with pytest.raises(Exception) as e:
        lambda_handler({
            "headers": {}
        }, None)
    assert str(e.value) == "Unauthorized"


@patch("main.api_gateway_client")
def test_lambda_handler_api_key_does_not_exist(mock_api_gateway_client):
    api_gateway_client_paginator = MagicMock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": []
    }]

    mock_api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    with pytest.raises(Exception) as e:
        lambda_handler({
            "headers": {
                "authorization": "bearer hello"
            }
        }, None)

    assert str(e.value) == "Unauthorized"


@patch("main.api_gateway_client")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "principal")
@patch("main.AWS_REGION", "us-east-1")
def test_lambda_handler_api_key_given_exists(mock_api_gateway_client):
    api_gateway_client_paginator = MagicMock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": [
            {
                "id": "alpha",
                "value": "hello",
                "tags": {
                    "foo": "bar",
                    "principal": "principal_id",
                    "context:bravo": "charlie"
                }
            }
        ]
    }]

    mock_api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    response = lambda_handler({
        "requestContext": {
            "accountId": "aws_account_id",
            "apiId": "api_id",
            "stage": "api_stage"
        },
        "headers": {
            "authorization": "bearer hello"
        }
    }, None)

    assert response == {
        "principalId": "principal_id",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": f"arn:aws:execute-api:us-east-1:aws_account_id:api_id/api_stage/*"
                }
            ]
        },
        "context": {
            "bravo": "charlie"
        },
        "usageIdentifierKey": "hello"
    }


@patch("main.api_gateway_client")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "doesnotexist")
@patch("main.AWS_REGION", "us-east-1")
def test_lambda_handler_api_key_given_exists_default_principal_id(mock_api_gateway_client):
    api_gateway_client_paginator = MagicMock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": [
            {
                "id": "alpha",
                "value": "hello",
                "tags": {
                    "foo": "bar",
                    "principal": "principal_id",
                    "context:bravo": "charlie"
                }
            }
        ]
    }]

    mock_api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    response = lambda_handler({
        "requestContext": {
            "accountId": "aws_account_id",
            "apiId": "api_id",
            "stage": "api_stage"
        },
        "headers": {
            "authorization": "bearer hello"
        }
    }, None)

    assert response == {
        "principalId": "foobar",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": f"arn:aws:execute-api:us-east-1:aws_account_id:api_id/api_stage/*"
                }
            ]
        },
        "context": {
            "bravo": "charlie"
        },
        "usageIdentifierKey": "hello"
    }


# fetch_api_key
@patch("main.api_gateway_client")
def test_fetch_api_key_missing(mock_api_gateway_client):
    api_gateway_client_paginator = MagicMock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": [
            {
                "id": "a",
                "value": "foo"
            }
        ]
    }]

    mock_api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    api_key = fetch_api_key("hello")

    assert api_key is None


@patch("main.api_gateway_client")
def test_fetch_api_key_present(mock_api_gateway_client):
    api_gateway_client_paginator = MagicMock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": [
            {
                "id": "a",
                "value": "foo"
            },
            {
                "id": "b",
                "value": "hello"
            }
        ]
    }]

    mock_api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    api_key = fetch_api_key("hello")

    assert api_key["id"] == "b"


# find_first_header_value
def test_find_first_header_value_absent():
    first_header_value = find_first_header_value({"headers": {"foo": "bar"}}, "hello")
    assert first_header_value is None


def test_find_first_header_value_present_case_sensitive():
    first_header_value = find_first_header_value({"headers": {"hello": "world"}}, "hello")
    assert first_header_value == "world"


def test_find_first_header_value_present_case_insensitive():
    first_header_value = find_first_header_value({"headers": {"Hello": "world"}}, "hello")
    assert first_header_value == "world"


def test_find_first_header_value_present_multiple():
    first_header_value = find_first_header_value({"headers": {"hello": "foo,bar"}}, "hello")
    assert first_header_value == "foo"


# find_api_key
def test_find_api_key_absent():
    api_key = find_api_key({"headers": {}})
    assert api_key is None


def test_find_api_key_present_not_bearer():
    api_key = find_api_key({"headers": {"authorization": "foobar hello"}})
    assert api_key is None


def test_find_api_key_present_bearer():
    api_key = find_api_key({"headers": {"authorization": "bearer hello"}})
    assert api_key == "hello"
