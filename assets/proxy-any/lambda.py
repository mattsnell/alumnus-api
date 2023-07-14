import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):

    # Helpful for debugging events from CloudWatch logs
    # print(json.dumps(event))

    # This is tough to read, but fails early if the required
    # 'uname' parameter is missing on the '/alumnus' resource.
    # Note: parameter validation on the API should eliminate
    # the need for this block, but it's wise to account for
    # known errors whenever possible.
    if (
        event['path'] == '/alumnus' and
        not event['queryStringParameters'] or
        event['path'] == "/alumnus" and
        event['queryStringParameters'] and
        "uname" not in event['queryStringParameters'].keys()
    ):
        logger.info('Missing uname query parameter, exiting')
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': 'uname is a required query parameter'
        }

    if event['httpMethod'] != 'GET':
        logger.info('{} not supported'.format(event['httpMethod']))
        return {
            'statusCode': 501,
            'headers': {
                'Content-Type': 'application/json'
            },
            'body': '{} not supported'.format(event['httpMethod'])
        }

    alumnus_data_processed = None

    # Mock data consisting of a list of dictionaries, this is
    # representative of alum data in a database.  Assume that
    # "uname" is unique in this example.
    alumni_data_source = [
        {
            'id': 1,
            'uname': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'johndoe@example.com',
            'gender': 'male'
        },
        {
            'id': 2,
            'uname': 'janedoe',
            'first_name': 'Jane',
            'last_name': 'Doe',
            'email': 'janedoe@example.com',
            'gender': 'Female'
        },
        {
            'id': 3,
            'uname': 'mds',
            'first_name': 'Matt',
            'last_name': 'Smith',
            'email': 'mds@example.com',
            'gender': 'Male'
        },
        {
            'id': 4,
            'uname': 'bobsmith',
            'first_name': 'Bob',
            'last_name': 'Smith',
            'email': 'bob@example.com',
            'gender': 'Male'
        },
    ]

    # In Lambda proxy integration, API Gateway maps the entire client
    # request to the input event parameter of the backend Lambda function
    #  https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    # This block handles path parameters as input.
    # If the method is GET and if pathParameters is not null, capture
    # the user name and query the data source for the alum's record.
    if (
        event['httpMethod'] == 'GET' and
        event['pathParameters']
    ):
        # The user name is extracted from the first level path param
        # specified by the client, anything beyond that is silently
        # ignored (should probably be handled differently)
        # This means 'frank' is extracted from '/alumnus/frank/foo'
        # and 'foo' isn't factored into the request.
        alumnus_username = event['pathParameters']['proxy'].split('/')[0]
        alumnus_data = get_alumnus(alumnus_username, alumni_data_source)

    # This block handles calls to the 'alumnus' resource
    # If the method is GET, the path is '/alumnus', and the client
    # specified input query parameters, capture the user name
    # and query the data source for the alum's record
    if (
        event['httpMethod'] == 'GET' and
        event['path'] == '/alumnus' and
        event['queryStringParameters']
    ):
        # Get the user name from the 'uname' query string
        alumnus_username = event['queryStringParameters']['uname']
        alumnus_data = get_alumnus(alumnus_username, alumni_data_source)

    # If we didn't match in either of the calls to get_alumnus
    # the value of alumnus_data is None, return No Content.
    if not alumnus_data:
        logger.info(f'{alumnus_username} not found, exiting')
        return {'statusCode': 204}

    # This block determines if additional query string parameters
    # were provided.  The only supported parameter is "field" and
    # is used to select the specific keys that will be returned to
    # the caller in a JSON object.
    #
    # Input to this function is the alum's record that was returned
    # from one of the calls to get_alumnus above.
    #
    # Example query string API call with additional fields:
    #   ?uname=frank&field=first_name&field=last_name
    if (
        event['multiValueQueryStringParameters'] and
        'field' in event['multiValueQueryStringParameters'].keys() and
        type(event['multiValueQueryStringParameters']['field']) is list
    ):
        field_filter = event['multiValueQueryStringParameters']['field']
        alumnus_data_filtered = filter_by_fields(field_filter, alumnus_data)

        # If the caller requested a non-existent key, filter_by_fields
        # returns with a value of None, return appropriate message.
        if not alumnus_data_filtered:
            logger.info(f'filter "{field_filter}" is invalid, exiting')
            return {
                'statusCode': 422,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': 'Invalid filter specified'
            }

        # If filter_by_fields was successful, set the value of our
        # return data to the output of filter_by_fields.
        alumnus_data_processed = alumnus_data_filtered

    # If the client didn't include filters in the request, set the
    # value of our return data to the output of get_alumnus
    if not alumnus_data_processed:
        alumnus_data_processed = alumnus_data

    # Return alumnus_data_processed to the caller.
    logger.debug(f'Result:\n {json.dumps(alumnus_data_processed)}')
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json'
        },
        'body': json.dumps(alumnus_data_processed)
    }


def get_alumnus(user_name, data_source):
    # Iterate over the data source and capture the alum's
    # information by matching the user_name provided by
    # the caller with the 'uname' key in the source data.
    # If there's no match, return value of None.
    alumnus = None
    for alum in data_source:
        if user_name == alum['uname']:
            alumnus = alum
            break
    return alumnus


def filter_by_fields(filter, data_source):
    # Using the filters provided by the caller, create/return
    # a new dictionary with only the keys/values requested.
    # If caller requests a non-existent key, return None.
    try:
        alumnus_filtered = {k: data_source[k] for k in filter}
    except KeyError:
        return None
    return alumnus_filtered
