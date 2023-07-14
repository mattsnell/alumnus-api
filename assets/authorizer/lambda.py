import boto3
import json
import logging
import os

secretsmanager = boto3.client('secretsmanager', region_name='us-east-1')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):

    # Example input event:
    # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-input.html
    # {
    #     "type": "TOKEN",
    #     "methodArn": "arn:aws:execute-api:us-east-1:000000000000:19ekpvp4c6/dev/GET/resource",
    #     "authorizationToken": "m2PSsz675otmFIoFbiFc4tEGEzM7I1K9"
    # }

    principal = "api_user"
    resource = event['methodArn']
    client_token = event['authorizationToken']
    secret = get_secret()

    if client_token == secret:
        response = generate_policy(principal, 'Allow', resource)
        logger.debug(json.dumps(response))
        return response
    else:
        response = generate_policy(principal, 'Deny', resource)
        logger.info('Client failed to provide valid authorization token')
        return response


# Retrieve secret value from a secret in AWS Secrets Manager.  This
# function expects there to be a 'SECRET_ARN' environment variable
# that refers to the secret.
def get_secret():
    secret_arn = os.environ['SECRET_ARN']
    response = secretsmanager.get_secret_value(SecretId=secret_arn)
    secret_string = response['SecretString']
    return secret_string

# Generate the policy to allow or deny invocation of the resource
def generate_policy(principal_id, effect, resource):
    # https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-lambda-authorizer-output.html
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        }
    }
    return policy
