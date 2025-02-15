
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed, TimeoutError
import io
from io import BytesIO
import json
import gzip
from os import cpu_count
import pandas as pd
import requests 
from requests.exceptions import RequestException
import time

from utils.util import *
from config.logger_config import logger  # Import the logger




# # Function to get block trace, transform and store in S3
# # Reducing the retries will improve overall performance as it won't hold up the other threads
# def fetch_transform_store_block_trace(rpc_url, rpc_number, block_number, s3, bucket_name, prefix, retries=2):
#     payload = {
#         "jsonrpc": "2.0",
#         "method": "debug_traceBlockByNumber",
#         "params": [hex(block_number), {}],
#         "id": 1
#     }

#     try:
#         for attempt in range(retries):
#             try:
#                 response = requests.post(rpc_url, json=payload, timeout=60)
#                 response.raise_for_status()
#                 trace = response.json()
                
#                 # Transform and store data
#                 if 'result' in trace:
#                     data = []
#                     for tx in trace['result']:
#                         tx_hash = tx['txHash']
#                         for structLog in tx['result']['structLogs']:
#                             storage = structLog.get('storage', {})
#                             state_growth_count = sum(1 for val1, val2 in storage.items() if is_null(val1) and not is_null(val2))
#                             data.append({
#                                 'BLOCK_NUMBER': block_number,
#                                 'TRANSACTION_HASH': tx_hash,
#                                 'OPCODE': structLog['op'],
#                                 'GAS': structLog['gas'],
#                                 'GAS_COST': structLog['gasCost'],
#                                 'STATE_GROWTH_COUNT': state_growth_count
#                             })
                    
#                     # Transform data
#                     df = pd.DataFrame(data)
                    
#                     # First aggregation level: Aggregate by TRANSACTION_HASH to get MAX_GAS and MIN_GAS
#                     transaction_agg = df.groupby(['BLOCK_NUMBER', 'TRANSACTION_HASH']).agg(
#                         MAX_GAS=('GAS', 'max'),
#                         MIN_GAS=('GAS', 'min')
#                     ).reset_index()

#                     # Second aggregation level: Aggregate by TRANSACTION_HASH and OPCODE
#                     opcode_agg = df.groupby(['BLOCK_NUMBER', 'TRANSACTION_HASH', 'OPCODE']).agg(
#                         OPCODE_COUNT=('OPCODE', 'size'),
#                         SUM_GAS_COST=('GAS_COST', 'sum'),
#                         STATE_GROWTH_COUNT=('STATE_GROWTH_COUNT', 'sum')
#                     ).reset_index()

#                     # Merge the two aggregation results
#                     merged_df = pd.merge(transaction_agg, opcode_agg, on=['BLOCK_NUMBER', 'TRANSACTION_HASH'])
                    
#                     # Store transformed data in S3
#                     s3_key = f"{prefix}{block_number}.parquet"
#                     buffer = io.BytesIO()
#                     merged_df.to_parquet(buffer, index=False)
#                     s3.put_object(Bucket=bucket_name, Key=s3_key, Body=buffer.getvalue())
                
#                 return True, block_number
#             except Exception as e:
#                 logger.error(f"Attempt {attempt + 1}/{retries} failed for block {block_number}: {e} - with rpc {rpc_number}")
#                 if attempt < retries - 1:
#                     time.sleep(2 ** attempt)  # Exponential backoff
#                 else:
#                     raise
#     except Exception as e:
#         logger.info(f"Block number {block_number} failed using rpc {rpc_number}")
#         return False, block_number



# # Fetch raw opcodes from RPC and store in S3
# def multi_thread_fetch_transform_store_block_trace(s3, bucket_name, prefix, rpc_url, rpc_number, blocks_list):
#     num_cpus = cpu_count()
#     logger.info(f"Number of CPUs available: {num_cpus}")

#     start_time = time.time()
#     with ThreadPoolExecutor(max_workers=num_cpus*4) as executor:
#         future_to_block = {executor.submit(fetch_transform_store_block_trace, rpc_url, rpc_number, block, s3, bucket_name, prefix): block for block in blocks_list}
#         for future in as_completed(future_to_block):
#             try:
#                 success, block_number = future.result(timeout=130)
#                 if success:
#                     logger.info(f'Block number {block_number} has been processed and stored by rpc {rpc_number}')
#                 else:
#                     logger.error(f"Failed to fetch and store block {block_number} with rpc {rpc_number}")
#             except TimeoutError:
#                 logger.error(f"TimeoutError for block {future_to_block[future]} with rpc {rpc_number}")
#             except Exception as e:
#                 logger.error(f"Exception occurred for block {future_to_block[future]} with rpc {rpc_number}: {e}")
#     end_time = time.time()
#     logger.info(f"Time taken to fetch, transform, and store traces for {str(len(blocks_list))} blocks with rpc {rpc_number}: {end_time - start_time:.2f} seconds")


# Store block traces in S3 in batches of x blocks per file 
def fetch_transform_store_block_trace(rpc_url, rpc_number, block_numbers, s3, bucket_name, prefix, retries=2):
    all_data = []
    failed_blocks = []

    for block_number in block_numbers:
        # logger.info(f"Fetching block {block_number} with rpc {rpc_number}")
        payload = {
            "jsonrpc": "2.0",
            "method": "debug_traceBlockByNumber",
            "params": [hex(block_number), {}],
            "id": 1
        }

        success = False
        for attempt in range(retries):
            try:
                response = requests.post(rpc_url, json=payload, timeout=60)
                response.raise_for_status()
                trace = response.json()
                
                # Transform data
                if 'result' in trace:
                    for tx in trace['result']:
                        tx_hash = tx['txHash']
                        for structLog in tx['result']['structLogs']:
                            storage = structLog.get('storage', {})
                            state_growth_count = sum(1 for val1, val2 in storage.items() if is_null(val1) and not is_null(val2))
                            all_data.append({
                                'BLOCK_NUMBER': block_number,
                                'TRANSACTION_HASH': tx_hash,
                                'OPCODE': structLog['op'],
                                'GAS': structLog['gas'],
                                'GAS_COST': structLog['gasCost'],
                                'STATE_GROWTH_COUNT': state_growth_count
                            })
                success = True
                break  # If successful, break the retry loop
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{retries} failed for block {block_number}: {e} - with rpc {rpc_number}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        if not success: 
            failed_blocks.append(block_number)

    # Process all collected data
    df = pd.DataFrame(all_data)
    
    # First aggregation level: Aggregate by TRANSACTION_HASH to get MAX_GAS and MIN_GAS
    transaction_agg = df.groupby(['BLOCK_NUMBER', 'TRANSACTION_HASH']).agg(
        MAX_GAS=('GAS', 'max'),
        MIN_GAS=('GAS', 'min')
    ).reset_index()

    # Second aggregation level: Aggregate by TRANSACTION_HASH and OPCODE
    opcode_agg = df.groupby(['BLOCK_NUMBER', 'TRANSACTION_HASH', 'OPCODE']).agg(
        OPCODE_COUNT=('OPCODE', 'size'),
        SUM_GAS_COST=('GAS_COST', 'sum'),
        STATE_GROWTH_COUNT=('STATE_GROWTH_COUNT', 'sum')
    ).reset_index()

    # Merge the two aggregation results
    merged_df = pd.merge(transaction_agg, opcode_agg, on=['BLOCK_NUMBER', 'TRANSACTION_HASH'])
    
    # Store transformed data in S3
    start_block = min(block_numbers)
    end_block = max(block_numbers)
    s3_key = f"{prefix}{start_block}_{end_block}.parquet"
    buffer = io.BytesIO()
    merged_df.to_parquet(buffer, index=False)
    s3.put_object(Bucket=bucket_name, Key=s3_key, Body=buffer.getvalue())

    # Append failed blocks in a zipped json file in S3
    if failed_blocks:
        failed_blocks_key = f"failed_blocks_{rpc_number}.jsonl.gz"

        try:
            # Try to get the existing file
            existing_file = s3.get_object(Bucket=bucket_name, Key=failed_blocks_key)
            with gzip.GzipFile(fileobj=BytesIO(existing_file['Body'].read()), mode='rb') as gz:
                existing_content = gz.read().decode('utf-8')
            existing_blocks = set(json.loads(line)['block'] for line in existing_content.splitlines())
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                existing_content = ""
                existing_blocks = set()
            else:
                raise

        # Prepare new data to append, excluding duplicates
        new_data = [json.dumps({"block": block}) + "\n" for block in failed_blocks if block not in existing_blocks]

        # Combine existing content with new data
        combined_content = existing_content + "".join(new_data)
        
        # Compress and store the updated content back to S3
        buffer = BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode='w') as gz:
            gz.write(combined_content.encode('utf-8'))

        buffer.seek(0)
        s3.put_object(Bucket=bucket_name, Key=failed_blocks_key, Body=buffer.getvalue())

        logger.info(f"Updated failed_blocks_{rpc_number}.jsonl.gz in S3 with {len(new_data)} new unique failed blocks")


    return True, block_numbers

# Multi thread fetch, transform and store block traces for batches of blocks instead of a single block at a time
def multi_thread_fetch_transform_store_block_trace(s3, bucket_name, prefix, rpc_url, rpc_number, blocks_list):
    num_cpus = cpu_count()
    logger.info(f"Number of CPUs available: {num_cpus}")

    # Group blocks into batches of batch_size
    batch_size = 20
    block_batches = [blocks_list[i:i+batch_size] for i in range(0, len(blocks_list), batch_size)]

    start_time = time.time()
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_blocks = {executor.submit(fetch_transform_store_block_trace, rpc_url, rpc_number, batch, s3, bucket_name, prefix): batch for batch in block_batches}
        for future in as_completed(future_to_blocks):
            try:
                success, block_numbers = future.result(timeout=130)
                if success:
                    logger.info(f'Blocks {min(block_numbers)} to {max(block_numbers)} have been processed and stored by rpc {rpc_number} to S3 bucket {bucket_name} with prefix {prefix}')
                else:
                    logger.error(f"Failed to fetch and store blocks {min(block_numbers)} to {max(block_numbers)} with rpc {rpc_number}")
            except TimeoutError:
                logger.error(f"TimeoutError for blocks {min(future_to_blocks[future])} to {max(future_to_blocks[future])} with rpc {rpc_number}")
            except Exception as e:
                logger.error(f"Exception occurred for blocks {min(future_to_blocks[future])} to {max(future_to_blocks[future])} with rpc {rpc_number}: {e}")
    end_time = time.time()
    logger.info(f"Time taken to fetch, transform, and store traces for {str(len(blocks_list))} blocks with rpc {rpc_number}: {end_time - start_time:.2f} seconds")
