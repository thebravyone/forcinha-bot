import json

def lambda_handler(event, context):
    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "hello world",
        }),
    }

if __name__ == "__main__":
    lambda_handler({}, None)
    pass