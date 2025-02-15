
import argparse
from dotenv import load_dotenv
import logging
import os
import platform
import time
import watchtower
from web3 import Web3
import sqlite3

from utils.util import *
from utils.process_data import *
from config.logger_config import logger  # Import the logger

# Load environment variables from .env file
load_dotenv()

# Snowflake connection details
secret = get_secret(user='notnotsez-peter')
table_name = os.getenv("TABLE_NAME")

# S3 connection details
s3 = boto3.client('s3')
BUCKET_NAME = os.getenv("BUCKET_NAME")
S3_PREFIX = os.getenv("S3_PREFIX")

# Main function to fetch and store recent blocks
def main(run_strategy, start_block=None, end_block=None, batch_size=100, rpc_number=0):
    # Retrieve the Ethereum RPC URL from environment variables
    rpc_url = os.getenv(f"RPC_URL_{rpc_number}")
    logger.info(f"RPC number {rpc_number}: {rpc_url}")
    if not rpc_url:
        raise ValueError(f"RPC_URL_{rpc_number} is not set. Please check your .env file.")

    # Connect to the blockchain RPC endpoint
    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 120}))

    try:
        start_time = time.time()

        if run_strategy == 'default':
            latest_block = web3.eth.block_number
            logger.info(f"Latest current block number: {str(latest_block)}")

            # Fetch the latest block number from Snowflake
            try:
                latest_snowflake_block_number = fetch_latest_block_number(secret, 'STAGING', table_name)
                logger.info(f"Latest block number from Snowflake: {str(latest_snowflake_block_number)}")
            except Exception as e:
                error_msg = f"Error fetching latest block numbers from Snowflake: {e}"
                logger.info(error_msg)
                return

            # Determine the start block based on the latest block number from Snowflake
            start_block = latest_snowflake_block_number + 1 if latest_snowflake_block_number else latest_block

        elif run_strategy == 'historical':
            latest_block = end_block
            logger.info('Run strategy: historical')
            logger.info(f'start block: {str(start_block)}')
            logger.info(f'end block: {str(end_block)}')

        range_start_block = start_block

        previous_block_range = None # Initialise the previous iteration's block range
        sleep_time = 1 # Initialize sleep time for exponential backoff 

        # Start iterating through the blocks in batches of batch_size
        while range_start_block < latest_block:
            reprocess = False
            range_end_block = min(range_start_block + batch_size, latest_block)
            current_block_range = (range_start_block, range_end_block)
            logger.info(f"Processing blocks {range_start_block} to {range_end_block} with rpc {rpc_number}...")

            try:
                blocks_list = list(range(range_start_block, range_end_block))
                multi_thread_fetch_transform_store_block_trace(s3, BUCKET_NAME, S3_PREFIX, rpc_url, rpc_number, blocks_list)
            except Exception as e:
                reprocess = True
                error_msg = f"Error fetching or pushing data for block range {range_start_block}-{range_end_block}: {e}"
                logger.error(error_msg)
                
                # Exponential backoff if the block range is the same as the previous one
                if current_block_range == previous_block_range:
                    time.sleep(sleep_time)
                    sleep_time *= 2  # Double the sleep time for the next retry
                else:
                    sleep_time = 1  # Reset sleep time if the block range is different

            if not reprocess:
                range_start_block += batch_size

            # Set previous_block_range to current_block_range for the next iteration
            previous_block_range = current_block_range

        end_time = time.time()
        success_msg = f"OPCODES data for blocks {start_block} to {end_block} stored in S3 in {end_time - start_time:.2f} seconds using rpc {rpc_number}."
        logger.info(success_msg)

    except Exception as e:
        error_msg = f"Unexpected error in main function: {e}"
        logger.error(error_msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch and store blockchain data.')
    parser.add_argument('run_strategy', choices=['default', 'historical'], help='The run strategy for this run. Choose default to load data for a daily load, historical for chunking historical blocks into batches for faster processing and multiple invocations of this script.')
    parser.add_argument('start_block', type=int, help='The start block for this run (inclusive of this block).')
    parser.add_argument('end_block', type=int, help='The end block for this run (not inclusive of this block).')
    parser.add_argument('batch_size', type=int, help='The number of blocks to process in one iteration of the the loop.')
    parser.add_argument('rpc_number', type=int, help='The rpc url to use for this run from .env')
    args = parser.parse_args()

    main(args.run_strategy, args.start_block, args.end_block, args.batch_size, args.rpc_number)
