import json
import boto3

def lambda_handler(event, context):
    data = {
        "test": "test2"
    }
    json_data = json.dumps(data)
    
    s3 = boto3.client('s3')
    bucket_name = 'grab-tools-stats'

    file_name = 'data.json'
    s3.put_object(Bucket=bucket_name, Key=file_name, Body=json_data)

    return {
        'statusCode': 200,
        'body': json.dumps('Stats updated')
    }
