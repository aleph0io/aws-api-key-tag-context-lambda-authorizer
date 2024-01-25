from unittest.mock import patch, Mock

from main import find_first_header_value
from main import find_api_key_in_request
from main import fetch_api_key
from main import lambda_handler


# lambda_handler
def test_lambda_handler_api_key_missing():
    try:
        lambda_handler({
            "headers": {}
        }, None)
    except Exception as e:
        assert str(e) == "Unauthorized"
    else:
        raise Exception("No exception thrown")


@patch("main.get_api_gateway_client")
@patch("main.get_api_key_cache_entry")
@patch("main.put_api_key_cache_entry")
def test_lambda_handler_api_key_does_not_exist(
        mock_put_api_key_cache_entry,
        mock_get_api_key_cache_entry,
        mock_get_api_gateway_client):
    mock_get_api_key_cache_entry.return_value = None
    mock_put_api_key_cache_entry.return_value = None

    api_gateway_client_paginator = Mock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": []
    }]

    api_gateway_client = Mock()
    api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    mock_get_api_gateway_client.return_value = api_gateway_client

    try:
        lambda_handler({
            "headers": {
                "authorization": "bearer hello"
            }
        }, None)
    except Exception as e:
        assert str(e) == "Unauthorized"
    else:
        raise Exception("No exception thrown")


@patch("main.current_time_epoch")
@patch("main.fetch_api_key")
@patch("main.get_api_key_cache_entry")
@patch("main.put_api_key_cache_entry")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "principal")
@patch("main.AWS_REGION", "us-east-1")
@patch("main.MAX_API_KEY_CACHE_AGE_SECONDS", 300)
def test_lambda_handler_api_key_given_exists_cached_not_expired(
        mock_put_api_key_cache_entry,
        mock_get_api_key_cache_entry,
        mock_fetch_api_key,
        mock_current_time_epoch):
    now = 1234567890

    mock_current_time_epoch.return_value = now

    mock_get_api_key_cache_entry.return_value = {
        "id": "alpha",
        "value": "hello",
        "timestamp": now - 10,
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    }

    mock_put_api_key_cache_entry.return_value = None

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

    mock_put_api_key_cache_entry.verify_called_with({
        "id": "alpha",
        "value": "hello",
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    })

    mock_fetch_api_key.assert_not_called()


@patch("main.current_time_epoch")
@patch("main.fetch_api_key")
@patch("main.get_api_key_cache_entry")
@patch("main.put_api_key_cache_entry")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "principal")
@patch("main.AWS_REGION", "us-east-1")
@patch("main.MAX_API_KEY_CACHE_AGE_SECONDS", 300)
def test_lambda_handler_api_key_given_exists_cached_expired(
        mock_put_api_key_cache_entry,
        mock_get_api_key_cache_entry,
        mock_fetch_api_key,
        mock_current_time_epoch):
    now = 1234567890

    mock_current_time_epoch.return_value = now

    mock_get_api_key_cache_entry.return_value = {
        "id": "alpha",
        "value": "hello",
        "timestamp": now - 3000,
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    }

    mock_put_api_key_cache_entry.return_value = None

    mock_fetch_api_key.return_value = {
        "id": "alpha",
        "value": "hello",
        "timestamp": now - 3000,
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    }

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

    mock_put_api_key_cache_entry.verify_called_with({
        "id": "alpha",
        "value": "hello",
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    })

    mock_fetch_api_key.verify_called_with("hello")

@patch("main.get_api_gateway_client")
@patch("main.get_api_key_cache_entry")
@patch("main.put_api_key_cache_entry")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "principal")
@patch("main.AWS_REGION", "us-east-1")
def test_lambda_handler_api_key_given_exists_not_cached(
        mock_put_api_key_cache_entry,
        mock_get_api_key_cache_entry,
        mock_get_api_gateway_client):
    mock_get_api_key_cache_entry.return_value = None
    mock_put_api_key_cache_entry.return_value = None

    api_gateway_client_paginator = Mock()
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

    api_gateway_client = Mock()
    api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    mock_get_api_gateway_client.return_value = api_gateway_client

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

    mock_put_api_key_cache_entry.verify_called_with({
        "id": "alpha",
        "value": "hello",
        "tags": {
            "foo": "bar",
            "principal": "principal_id",
            "context:bravo": "charlie"
        }
    })


@patch("main.get_api_gateway_client")
@patch("main.get_api_key_cache_entry")
@patch("main.put_api_key_cache_entry")
@patch("main.DEFAULT_PRINCIPAL_ID", "foobar")
@patch("main.PRINCIPAL_ID_TAG_NAME", "doesnotexist")
@patch("main.AWS_REGION", "us-east-1")
def test_lambda_handler_api_key_given_exists_default_principal_id(
        mock_put_api_key_cache_entry,
        mock_get_api_key_cache_entry,
        mock_get_api_gateway_client):
    mock_get_api_key_cache_entry.return_value = None
    mock_put_api_key_cache_entry.return_value = None

    api_gateway_client_paginator = Mock()
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

    api_gateway_client = Mock()
    api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    mock_get_api_gateway_client.return_value = api_gateway_client

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
@patch("main.get_api_gateway_client")
def test_fetch_api_key_missing(mock_get_api_gateway_client):
    api_gateway_client_paginator = Mock()
    api_gateway_client_paginator.paginate.return_value = [{
        "items": [
            {
                "id": "a",
                "value": "foo"
            }
        ]
    }]

    api_gateway_client = Mock()
    api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    mock_get_api_gateway_client.return_value = api_gateway_client

    api_key = fetch_api_key("hello")

    assert api_key is None


@patch("main.get_api_gateway_client")
def test_fetch_api_key_present(mock_get_api_gateway_client):
    api_gateway_client_paginator = Mock()
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

    api_gateway_client = Mock()
    api_gateway_client.get_paginator.return_value = api_gateway_client_paginator

    mock_get_api_gateway_client.return_value = api_gateway_client

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
@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(plain)")
def test_find_api_key_authorization_bearer_absent():
    api_key = find_api_key_in_request({"headers": {}})
    assert api_key is None


@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(plain)")
def test_find_api_key_authorization_bearer_present_not_bearer():
    api_key = find_api_key_in_request({"headers": {"authorization": "foobar hello"}})
    assert api_key is None


@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(plain)")
def test_find_api_key_authorization_bearer_present_plain_bearer():
    api_key = find_api_key_in_request({"headers": {"authorization": "bearer hello"}})
    assert api_key == "hello"


@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(base64)")
def test_find_api_key_authorization_bearer_present_base64_bearer():
    api_key = find_api_key_in_request({"headers": {"authorization": "bearer aGVsbG8="}})
    assert api_key == "hello"


@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(plain),header:alpha-bravo-charlie()")
def test_find_api_key_present_first_one_wins():
    api_key = find_api_key_in_request({
        "headers": {
            "authorization": "bearer zulu",
            "alpha-bravo-charlie": "yankee"
        }
    })
    assert api_key == "zulu"


@patch("main.AUTHORIZATION_PLAN", "authorization:bearer(plain),header:alpha-bravo-charlie()")
def test_find_api_key_present_second_one_works():
    api_key = find_api_key_in_request({
        "headers": {
            "alpha-bravo-charlie": "yankee"
        }
    })
    assert api_key == "yankee"


@patch("main.AUTHORIZATION_PLAN", "header:alpha-bravo-charlie()")
def test_find_api_key_header_present():
    api_key = find_api_key_in_request({"headers": {"alpha-bravo-charlie": "yankee"}})
    assert api_key == "yankee"


@patch("main.AUTHORIZATION_PLAN", "header:alpha-bravo-charlie()")
def test_find_api_key_header_absent():
    api_key = find_api_key_in_request({"headers": {}})
    assert api_key is None
