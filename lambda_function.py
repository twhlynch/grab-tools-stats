import json
import requests
import boto3

SERVER_URL = "https://api.slin.dev/grab/v1/"
PAGE_URL = "https://grab-tools.live/"
VIEWER_URL = "https://grabvr.quest/levels/viewer/"
FORMAT_VERSION = "100"
S3 = boto3.client('s3')
BUCKET_NAME = 'grab-tools-stats'

def write_json_file(filename, data):
    S3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=data)

def get_all_verified(stamp=''):
    verified = []
    while True:
        url = f"{SERVER_URL}list?max_format_version={FORMAT_VERSION}&type=ok&page_timestamp={stamp}"
        data = requests.get(url).json()
        verified.extend(data)
        if "page_timestamp" in data[-1]:
            stamp = data[-1]["page_timestamp"]
        else:
            break
    return verified

def lambda_handler(event, context):
    write_json_file('all_verified.json', get_all_verified())

    return {
        'statusCode': 200,
        'body': json.dumps('Stats updated')
    }
