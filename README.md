# aws-api-key-tag-context-lambda-authorizer [![integration](https://github.com/aleph0io/aws-api-key-tag-context-lambda-authorizer/actions/workflows/integration.yml/badge.svg)](https://github.com/aleph0io/aws-api-key-tag-context-lambda-authorizer/actions/workflows/integration.yml)

Implements an [AWS API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html) [Lambda Authorizer](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html) that copies API key tags to request context for downstream processing.

## Introduction

Out of the box, the authorizer performs the following steps:

1. Unpacks the API key from a bearer token (e.g., `Authorization: bearer $API_TOKEN`). The API token appears in plain text and is not base64-encoded. If not found, then unauthorized.
2. Looks up the API key using the [`GetApiKeys`](https://docs.aws.amazon.com/apigateway/latest/api/API_GetApiKeys.html) endpoint. If not found, then unauthorized.
3. Extracts data from API key [tags](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-tagging.html) and setting request principal ID, appending to context, etc.
4. Returns these metadata along with a policy that grants access to all methods in the requesting API.

This allows implementations to encode important metadata in API key tags (e.g., subscription plan, billing ID, etc.) and then access that data downstream in [mapping templates](https://docs.aws.amazon.com/apigateway/latest/developerguide/models-mappings.html), [access logging](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-mapping-template-reference.html), and so on via the `$context` request parameter.

The included `cfn-deploy.yml` [SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-specification.html) [Template](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-reference.html) can be used to deploy the authorizer.

The included `.github/workflows/deployment.yml.example` [GitHub Actions workflow](https://docs.github.com/en/actions) can be used to implement [continuous delivery](https://en.wikipedia.org/wiki/Continuous_delivery).

## Use Cases

### Metered Billing

In [metered billing](https://stripe.com/docs/billing/subscriptions/usage-based), API users are charged based on usage. This requires APIs to track usage on a per-user basis.

Applications can append subscription ID, user ID, and other metadata to API Keys at key creation time. Next, they can make these data available in [access logs](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-mapping-template-reference.html) via the `$context` request parameter. Finally, they can report usage to using a [lambda log subscription filter](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/SubscriptionFilters.html#LambdaFunctionExample) on the access logs.

### Multitenant Usage Tracking

It's important to provide customers with up-to-date usage information, particularly for APIs with hard quotas or metered billing. When multiple customers are using the same API, adding customer IDs to access logs allows for real-time usage information simply through log analysis.

## Recommended Developer Workflow

Authentication and Authorization are complex, so finding a (preferably simple) developer workflow that allows total control over deployment lifecycle is key. Find a proposed developer workflow below.

* **Fork this repo.** Needs differ, so keeping a separate copy to customize is useful. At the very least, this will allow total control over CI/CD.
* **Maintain a branch for each deployed Lambda authorizer.** This ensures that different authorizers with different logic are kept separate.
* **Use Continuous Delivery to deploy updates.** Enable CD on each branch by copying and modifying `.github/workflows/deployment.yml.example` to run on pushes to the appropriate branch(es). Individual branches can be updated separately, giving the user total control over deployment lifecycle.
* **Deploy to a fixed Lambda Alias.** For example, the default is `stag`. Configure a non-production API stage to use this alias, which allows easy testing.
* **Promote manually.** Configure the production API stage to use a different alias, e.g., `prod`. After testing is complete, point the `prod` alias at the same version as `stag`, thus promoting the staging code to production.

The authorizer and CloudFormation template support this workflow out of the box.

## Customization

### CloudFormation Parameters

The implementation supports several important customizations out of the box in the form of CloudFormation template parameters:

* `FunctionName` - An explicit name for the authorizer Lambda function. Useful to make ARN predictable. If left blank, a name will be generated automatically.
* `PrincipalIdTagName` - The API key tag name to extract the request [`principalId`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html) from.
* `ContextTagPrefix` - A prefix to use to decide which API key tags to include in request context. The prefix value is removed from tag keys before copying to request context. If left blank, then all tags are copied to request context without modification.
* `DefaultPrincipalId` - The default value to use for [`principalId`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html) if the given `PrincipalIdTagName` tag is missing. Leave blank to cause authentication to fail in this case.
* `AliasName` - The name of the [Lambda alias](https://docs.aws.amazon.com/lambda/latest/dg/configuration-aliases.html) to publish automatically on deploy. If left blank, then no alias is published.
* `VersionDescription` - The description to attach to the published [Lambda version](https://docs.aws.amazon.com/lambda/latest/dg/configuration-versions.html). If the `AliasName` parameter is blank, then this value is ignored. This is typically used in continuous delivery to label each version with its associated source code version.

### Other

Of course, users are free to modify however they like, but the following changes are expected:

* Change approach to extracting API key (e.g., `x-api-key` header instead of bearer token)
* Different approaches to loading API keys, e.g., [`customerId`](https://docs.aws.amazon.com/apigateway/latest/api/API_GetApiKeys.html#API_GetApiKeys_RequestSyntax)
* Custom access policies
* Append additional, bespoke request context
* Export authorizer ARN from `cfn-deploy.yml`

## Considerations

### GetApiKeys Throttling

The authorizer looks up API keys using the [`GetApiKeys`](https://docs.aws.amazon.com/apigateway/latest/api/API_GetApiKeys.html) endpoint. This endpoint is [throttled](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html#api-gateway-control-service-limits-table) at 10 requests per second, with a burst of 40 requests per second. For this reason, it's recommended to enable [authorization policy caching](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html#api-gateway-lambda-authorizer-flow) to manage authentication volume.

API keys are loaded at 500 per page, so API key loading is reasonably efficient. However, applications above a certain volume of API keys and request traffic may get throttled, even after enabling authorization policy caching. Note that there is a hard limit of [10,000 keys per account region](https://docs.aws.amazon.com/apigateway/latest/developerguide/limits.html#api-gateway-execution-service-limits-table).

Users experiencing throttling should consider other approaches to API key lookup, such as caching keys in a data store (e.g., [DynamoDB](https://aws.amazon.com/dynamodb/)) to reduce calls to the `GetApiKeys` endpoint.

## Future Features

Concepts for future features are captured as issues in this repository. If you have an idea for a new feature, please drop an issue!
