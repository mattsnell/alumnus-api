from aws_cdk import (
    # Aspects,
    Duration,
    Stack,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_apigateway as apigw,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct
from cdk_nag import NagSuppressions
class AlumnusApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Function handling the 'GET' API example
        lambda_get_function = _lambda.Function(
            self, "ProxyGetHandler",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("assets/proxy-get"),
            handler="lambda.handler",
        )

        # Function handling the 'ANY' API example
        lambda_any_function = _lambda.Function(
            self, "ProxyAnyHandler",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("assets/proxy-any"),
            handler="lambda.handler",
        )

        # AWS Secrets Manager secret, this contains the authorization
        # token that clients must provide to invoke the API
        rest_secret = secretsmanager.Secret(
            self, "Secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True
            )
        )

        # Function handling the token-based API Gateway authorizer
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-use-lambda-authorizer.html
        # This relies on the rest_secret defined above, the ARN of the
        # secret is configured in a Lambda environment variable.  The
        # the function reads the variable to get the secret.
        lambda_authorizer_function = _lambda.Function(
            self, "TokenAuthenticationHandler",
            runtime=_lambda.Runtime.PYTHON_3_10,
            code=_lambda.Code.from_asset("assets/authorizer"),
            handler="lambda.handler",
            environment={
                "SECRET_ARN": rest_secret.secret_arn
            }
        )

        # Grant lambda_authorizer_function read access to rest_secret
        rest_secret.grant_read(lambda_authorizer_function)

        # Define the API Gateway Lambda authorizer to manage access
        # to the methods that are defined below.  This specifies
        # that lambda_authorizer_function drives the authorization
        rest_get_authorizer = apigw.TokenAuthorizer(
            self, "GetTokenAuthorizer",
            handler=lambda_authorizer_function,
            results_cache_ttl=Duration.seconds(0)
        )

        rest_any_authorizer = apigw.TokenAuthorizer(
            self, "AnyTokenAuthorizer",
            handler=lambda_authorizer_function,
            results_cache_ttl=Duration.seconds(0)
        )

        # Log group to contain the API Gateway access logs.  Per best
        # practices, all API access should be logged.
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html
        log_group = logs.LogGroup(self, "LogGroup")

        # A REST API in API Gateway is a collection of resources and methods that are
        # integrated with backend HTTP endpoints, Lambda functions, or other AWS services
        # https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html
        rest_api = apigw.LambdaRestApi(
            self, "RestApiGet",
            handler=lambda_get_function,
            rest_api_name="Alumnus GET API Example",
            cloud_watch_role=True,
            proxy=False,
            deploy_options=apigw.StageOptions(
                stage_name="dev",
                logging_level=apigw.MethodLoggingLevel.INFO,
                metrics_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True
                )
            ),
        )

        # Define the 'alumnus' resource with a 'GET' method
        alumni_api = rest_api.root.add_resource("alumnus")
        alumni_api.add_method(
            "GET",apigw.LambdaIntegration(lambda_get_function),
            # Set the 'uname' query string parameter to required
            request_parameters={
                "method.request.querystring.uname": True
            },
            request_validator_options=apigw.RequestValidatorOptions(
                validate_request_parameters=True
            ),
            authorizer=rest_get_authorizer
            )
        # Define the 'uname' path parameter
        alumni_api_uname = alumni_api.add_resource("{uname}")
        alumni_api_uname.add_method(
            "GET", apigw.LambdaIntegration(lambda_get_function),
            authorizer=rest_get_authorizer
            )

        # Create another API to demonstrate the 'ANY' method and
        # using a greedy path parameter ({proxy+})
        rest_api_any = apigw.LambdaRestApi(
            self, "RestApiAny",
            handler=lambda_any_function,
            rest_api_name="Alumnus ANY API Example",
            cloud_watch_role=True,
            proxy=False,
            deploy_options=apigw.StageOptions(
                stage_name="dev",
                logging_level=apigw.MethodLoggingLevel.INFO,
                metrics_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True
                )
            ),
        )

        # Define the 'alumnus' resource with an 'ANY' method
        alumni_api_resource = rest_api_any.root.add_resource("alumnus")
        alumni_api_resource.add_method("ANY",apigw.LambdaIntegration(lambda_any_function),
            # Set the 'uname' query string parameter to required
            request_parameters={
                "method.request.querystring.uname": True
            },
            request_validator_options=apigw.RequestValidatorOptions(
                validate_request_parameters=True
            ),
            authorizer=rest_any_authorizer)
        # Define the greedy path parameter with an 'ANY' method
        alumni_api_resource.add_proxy(
            default_integration=apigw.LambdaIntegration(lambda_any_function),
            any_method=True,
            default_method_options=apigw.MethodOptions(
                authorizer=rest_any_authorizer
                )
            )

        # Adding resource specific cdk_nag suppressions
        # Suppressions for API Gateway REST APIs
        NagSuppressions.add_resource_suppressions(
            [rest_api,rest_api_any],
            [
                {
                    'id': 'AwsSolutions-COG4',
                    'reason': 'Using a Lambda token based authorizer instead of a Cognito user pool for this demo/example.  Cognito is suggested for production use.'
                },
                {
                    'id': 'AwsSolutions-APIG3',
                    'reason': 'AWS WAFv2 is not a component in this demo/example, this is not a production environment.'
                },
                {
                    'id': 'AwsSolutions-IAM4',
                    'reason': 'AmazonAPIGatewayPushToCloudWatchLogs managed policy is being used to provide write permissions to CloudWatch Logs.'
                },
                {
                    'id': 'AwsSolutions-APIG2',
                    'reason': 'Request validation is not required in this limited demo/example.'
                }
            ],
            apply_to_children=True
        )
        
        # Suppressions for Lambda functions
        NagSuppressions.add_resource_suppressions(
            [lambda_get_function,lambda_any_function,lambda_authorizer_function],
            [
                {
                    'id': 'AwsSolutions-IAM4',
                    'reason': 'AWSLambdaBasicExecutionRole managed policy is being used to provide write permissions to CloudWatch Logs.'
                }
            ],
            apply_to_children=True
        )
        
        # Suppression for Secrets Manager
        NagSuppressions.add_resource_suppressions(
            [rest_secret],
            [
                {
                    'id': 'AwsSolutions-SMG4',
                    'reason': 'This is a demo/example, the API Gateway authorizer would be replaced by Amazon Cognito in production and this secret would be dropped'
                }
            ]
        )
