
import boto3
from botocore.exceptions import ClientError
import concurrent.futures
from itertools import islice
import json
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
import sqlite3

from config.logger_config import logger  # Import the logger

# Get secret from AWS Secret Manager
def get_secret(user='notnotsez'):

    secret_name = f'snowflake-user-{user}'

    region_name = "ap-southeast-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    # Decrypts secret using the associated KMS key.
    secret = json.loads(get_secret_value_response['SecretString'])

    return secret


# Format long numbers with comma notation
def format_number_with_commas(number):
    return "{:,}".format(number)


# Utility function to create a Snowflake connection
def get_snowflake_connection(secret, schema):
    return snowflake.connector.connect(
        user=secret['user'],
        password=secret['password'],
        account=secret['account'],
        warehouse=secret['warehouse'],
        database='ARBITRUM_NOVA',
        schema=schema,
        login_timeout=30  # Increase the timeout for login
    )


# Fetch the latest timestamp and block number from the Snowflake table
def fetch_latest_block_number(secret, schema, table_name):
    conn = get_snowflake_connection(secret, schema)
    query = f"SELECT MAX(block_number) AS max_block FROM {table_name}"
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0]


# Function to check if a string represents a null value (all zeros)
def is_null(value):
    return value == '0000000000000000000000000000000000000000000000000000000000000000'


# Fetch failed blocks from Snowflake table
def fetch_failed_blocks(secret, schema, table_name):
    conn = get_snowflake_connection(secret, schema)
    query = f"SELECT block_number FROM {table_name}"
    cursor = conn.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    result_list = [item[0] for item in result]
    cursor.close()
    conn.close()
    return result_list


# Function to perform delta append using pandas to_sql
def delta_append(secret, schema, table_name, df):
    conn = get_snowflake_connection(secret, schema)
    cursor = conn.cursor()

    # Append new data using write_pandas
    if not df.empty:
        success, nchunks, nrows, _ = write_pandas(conn, df, table_name)
        if success:
            logger.info(f"Inserted {nrows} rows into {table_name}")
        else:
            logger.info(f"Failed to insert data into {table_name}")

    cursor.close()
    conn.close()


# Don't forget to close the connection when you're done
# This could be at the end of your script or in a function that's called when processing is complete
def cleanup_db(conn):
    if conn:
        try:
            conn.close()
            logger.info("Successfully closed connection to temporary SQLite database")
        except sqlite3.Error as e:
            logger.error(f"Error closing connection to temporary SQLite database: {e}")



def get_unprocessed_s3_objects(s3, bucket_name, prefix, last_processed_block):
    try:
        objects = []
        paginator = s3.get_paginator('list_objects_v2')
        
        operation_parameters = {
            'Bucket': bucket_name,
            'Prefix': prefix,
        }
        if last_processed_block is not None:
            operation_parameters['StartAfter'] = str(last_processed_block)
        
        page_iterator = paginator.paginate(**operation_parameters)
        
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Filter out the directory object and where the block number is greater than the last processed block
                    if obj['Size'] > 0:
                        block_number = int(obj['Key'].split('/')[-1].split('.')[0])
                        if last_processed_block is None or block_number > int(last_processed_block):
                            tags = s3.get_object_tagging(Bucket=bucket_name, Key=obj['Key'])
                            if not any(tag['Key'] == 'processed' and tag['Value'] == 'true' for tag in tags['TagSet']):
                                objects.append(obj)

        # Sort objects after last_processed_block
        sorted_objects = sorted(objects, key=lambda x: int(x['Key'].split('/')[-1].split('.')[0]))

        logger.info(f"Found {len(sorted_objects)} unprocessed objects in S3 to process")
        
        return sorted_objects
    except ClientError as e:
        logger.error(f"Error fetching objects from S3: {e}")
        raise

def mark_s3_object_as_processed(s3, bucket_name, key):
    try:
        s3.put_object_tagging(
            Bucket=bucket_name,
            Key=key,
            Tagging={'TagSet': [{'Key': 'processed', 'Value': 'true'}]}
        )
    except ClientError as e:
        logger.error(f"Error marking object as processed: {e}")
        raise


def delete_processed_s3_objects(s3, bucket_name, prefix):
    try:
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        delete_keys = []
        for page in page_iterator:
            # obj = page.get('Contents', [])[0]
            for obj in page.get('Contents', []):
                if obj['Size'] > 0:
                    try:
                        tags = s3.get_object_tagging(Bucket=bucket_name, Key=obj['Key'])
                        if any(tag['Key'] == 'processed' and tag['Value'] == 'true' for tag in tags['TagSet']):
                            delete_keys.append({'Key': obj['Key']})
                    except ClientError as e:
                        logger.error(f"Error checking object {obj['Key']}: {e}")

            perform_batch_delete(s3, bucket_name, delete_keys) # perform batch delete every 1000 objects 
            delete_keys = []

        # Delete any remaining objects
        if delete_keys:
            perform_batch_delete(s3, bucket_name, delete_keys)

    except ClientError as e:
        logger.error(f"Error listing objects for deletion: {e}")

def perform_batch_delete(s3, bucket_name, delete_keys):
    try:
        response = s3.delete_objects(
            Bucket=bucket_name,
            Delete={'Objects': delete_keys, 'Quiet': False}
        )
        deleted = len(response.get('Deleted', []))
        errors = len(response.get('Errors', []))
        logger.info(f"Batch delete: {deleted} objects deleted, {errors} errors")
    except ClientError as e:
        logger.error(f"Error in batch delete: {e}")