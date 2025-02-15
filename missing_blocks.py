

from dotenv import load_dotenv
import os
import time
from web3 import Web3
import argparse
import platform
import logging
from datetime import datetime

from utils.util import *
from utils.process_data import *

# Load environment variables from .env file
load_dotenv()

# Snowflake connection details
secret = get_secret(user='notnotsez-peter')
table_name = os.getenv("TABLE_NAME")

# Configure logging
logs_folder = 'logs'
os.makedirs(logs_folder, exist_ok=True)
current_datetime = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
log_filename = os.path.join(logs_folder, f'log_{current_datetime}.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# Define global list for failed blocks
global global_failed_blocks_list_prev
global global_failed_blocks_list_curr
global_failed_blocks_list_prev = []
global_failed_blocks_list_curr = []


# Main function to fetch and store recent blocks
def main(batch_size=100, rpc_number=0):

    # Retrieve the Ethereum RPC URL from environment variables
    rpc_url = os.getenv(f"RPC_URL_{rpc_number}")
    if not rpc_url:
        raise ValueError(f"RPC_URL_{rpc_number} is not set. Please check your .env file.")

    # Connect to the blockchain RPC endpoint
    web3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={'timeout': 30}))

    try:
        start_time = time.time()

        missing_blocks_df = pd.read_csv('data/missing_blocks.csv')
        missing_blocks_list = missing_blocks_df.iloc[:, 0].tolist()

        start_block = missing_blocks_list[0]
        end_block = latest_block = missing_blocks_list[-1]
        print('Run strategy: historical')
        print('start block:', str(start_block))
        print('end block:', str(end_block))

        range_start_block = start_block

        
        previous_block_range = None # Initialise the previous iteration's block range
        sleep_time = 1 # Initialize sleep time for exponential backoff 

        # Start iterating through the blocks in batches of batch_size
        while range_start_block < latest_block:
            reprocess = False
            range_end_block = min(range_start_block + batch_size, latest_block)
            current_block_range = (range_start_block, range_end_block)
            print(f"Processing missing blocks...")

            try:
                blocks_list = list(range(range_start_block, range_end_block))
                fetch_and_push_raw_opcodes_for_block_range(secret, table_name, rpc_url, rpc_number, blocks_list)
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
        success_msg = f"OPCODES data for blocks {start_block} to {end_block} written to Snowflake in {end_time - start_time:.2f} seconds."
        logger.info(success_msg)

        print(f"Global failed blocks retry list: {global_failed_blocks_list_curr}")
        global_failed_blocks_list_prev = global_failed_blocks_list_curr
        global_failed_blocks_list_curr = []

        if len(global_failed_blocks_list_prev) < 1000:
            try:
                logger.info("Main script finished running, now processing failed blocks...")
                fetch_and_push_raw_opcodes_for_block_range(secret, table_name, rpc_url, rpc_number, global_failed_blocks_list_prev)
            except Exception as e:
                error_msg = f"Error fetching or pushing data for failed blocks retry list: {e}"
                logger.error(error_msg)
        else: 
            error_msg = f"Global failed blocks retry list too large. Something has gone wrong. Please investigate!!"


    except Exception as e:
        error_msg = f"Unexpected error in main function: {e}"
        logger.error(error_msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fetch and store blockchain data.')
    parser.add_argument('batch_size', type=int, help='The number of blocks to process in one iteration of the the loop.')
    parser.add_argument('rpc_number', type=int, help='The rpc url to use for this run from .env')
    args = parser.parse_args()
    main(args.batch_size, args.rpc_number)