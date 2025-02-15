
import json
import pandas as pd
import requests
from web3 import Web3

from utils.process_data import *

# Replace with your QuickNode RPC URL
# RPC_URL = "https://purple-icy-diamond.nova-mainnet.quiknode.pro/891fee6038fca38ffe5e3da5c8ca3352e6e6be77"
RPC_URL = "https://red-side-seed.nova-mainnet.quiknode.pro/34758e88cb1015be06f730d4007e9238872b391f/"

web3 = Web3(Web3.HTTPProvider(RPC_URL))


# Function to get block trace
def get_block_trace(rpc_url, block_number):
    payload = {
        "jsonrpc": "2.0",
        "method": "debug_traceBlockByNumber",
        "params": [hex(block_number), {}],
        "id": 1
    }
    response = requests.post(rpc_url, json=payload)
    logger.info(response.json()['result'][0]['result']['structLogs'])
    return response.json()


# Replace with the block number you want to trace
block_number = 1234567
trace = get_block_trace(RPC_URL, block_number)


import requests
import json


# Process and print the trace data
if 'result' in trace:
    for tx in trace['result']:
        print(f"Transaction Hash: {tx['txHash']}")
        print(f"Gas Used: {tx['result']['gas']}")
        for structLog in tx['result']['structLogs']:
            print(f"Opcode: {structLog['op']}, Gas: {structLog['gas']}, Gas Cost: {structLog['gasCost']}")
            if 'storage' in structLog:
                print("Storage:")
                for key, value in structLog['storage'].items():
                    print(f"  {key}: {value}")
else:
    print("Error in fetching trace data")




data = [
    ('0000000000000000000000000000000000000000000000000000000000000000', '0000000000000000000000000000000000000000000000000000000000000000'),
    ('0000000000000000000000000000000000000000000000000000000000000008', '6381d4f900000000000000000013d471b575000000000003caa2a7b041e6b57f')
]

# Function to check if a string represents a null value (all zeros)
def is_null(value):
    return value == '0000000000000000000000000000000000000000000000000000000000000000'

# Count instances where the second element changes from null to non-null
count_null_to_non_null = sum(1 for _, val in data if not is_null(val))

print(f'Null to non-null instances = {count_null_to_non_null}')
