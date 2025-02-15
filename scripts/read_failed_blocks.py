
import json
import gzip
import boto3
import os 
from dotenv import load_dotenv
from io import BytesIO
from botocore.exceptions import ClientError


# Load environment variables from .env file
load_dotenv()


# S3 connection details
s3 = boto3.client('s3')
bucket_name = os.getenv("BUCKET_NAME")

def read_failed_blocks(s3, bucket_name, key):
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        with gzip.GzipFile(fileobj=BytesIO(response['Body'].read()), mode='rb') as gz:
            content = gz.read().decode('utf-8')
            for line in content.splitlines():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    print(f"Error decoding JSON: {line}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []
        else:
            raise

# Usage:
for failed_block in read_failed_blocks(s3, bucket_name, 'failed_blocks.jsonl.gz'):
    print(f"Block {failed_block['block']}")