
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import schedule
import sqlite3
import pandas as pd
import json
from dotenv import load_dotenv
from utils.util import *
from config.logger_config import logger
import time 

load_dotenv()

# S3 connection details
s3 = boto3.client('s3')
BUCKET_NAME = os.getenv("BUCKET_NAME")
S3_PREFIX = os.getenv("S3_PREFIX")

def push_to_snowflake(s3, bucket_name, prefix):
    logger.info("Starting daily snowflake push")

    # Get the last processed block from Snowflake
    secret = get_secret(user='notnotsez-peter')
    table_name = os.getenv("TABLE_NAME")
    # last_processed_block = fetch_latest_block_number(secret, 'STAGING', table_name)
    last_processed_block = None

    # Get unprocessed objects from S3
    unprocessed_objects = get_unprocessed_s3_objects(s3, bucket_name, prefix, last_processed_block) 

    if not unprocessed_objects:
        logger.info("No new data to process")
        return

    def process_batch(batch):
        df_list = [pd.read_parquet(f"s3://{BUCKET_NAME}/{obj['Key']}") for obj in batch]
        combined_df = pd.concat(df_list, ignore_index=True)
        delta_append(secret, 'STAGING', table_name, combined_df)
        for obj in batch:
            mark_s3_object_as_processed(s3, BUCKET_NAME, obj['Key'])

    # 100 blocks per batch
    batch_size = 100  # Adjust based on average file size and memory constraints, can try up to 1000
    batches = [unprocessed_objects[i:i + batch_size] for i in range(0, len(unprocessed_objects), batch_size)]

    with ThreadPoolExecutor(max_workers=8) as executor: # try up to 32 workers 
        futures = [executor.submit(process_batch, batch) for batch in batches]
        for future in as_completed(futures):
            future.result()  # This will raise any exceptions that occurred

    delete_processed_s3_objects(s3, BUCKET_NAME, S3_PREFIX)

    logger.info("Daily Snowflake push completed")


# Schedule the job to run daily at 3:00 PM machine time (3:00 PM UTC = 01:00 AM AEST)
schedule.every().day.at("15:00").do(push_to_snowflake, s3, BUCKET_NAME, S3_PREFIX)

if __name__ == "__main__":
    logger.info("Scheduler started")
    while True:
        schedule.run_pending()
        time.sleep(60)  # Sleep for 60 seconds before checking schedule again


# Testing
# push_to_snowflake(s3, BUCKET_NAME, S3_PREFIX)