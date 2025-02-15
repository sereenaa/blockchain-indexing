
import os
import cryo
from dotenv import load_dotenv
import json
import requests
import time

# Load environment variables from .env file
load_dotenv()

# Retrieve the Ethereum RPC URL from environment variables
rpc_url = os.getenv("RPC_URL")

# Collect blockchain data using the cryo library and return it as a pandas DataFrame
# Specifying blocks range and output format
opcodes_data = cryo.collect(
    "geth_opcodes", 
    blocks=["53155869:53155879"], 
    rpc=rpc_url, 
    output_format="pandas", 
    hex=True,
    requests_per_second=100,
    max_retries=10, 
    initial_backoff=1000,
    include_columns=['block_number']
)


df = opcodes_data[opcodes_data['block_number']==53155869]


# Collect blockchain data using the cryo library and return it as a pandas DataFrame
# Specifying blocks range and output format
start_time = time.time()
vm_traces_data = cryo.collect(
    "vm_traces", 
    blocks=["53155869:53156869"], 
    rpc=rpc_url, 
    output_format="pandas", 
    hex=True,
    requests_per_second=100,
    max_retries=10, 
    initial_backoff=1000,
    include_columns=['block_number']
)

payload = json.dumps({
  "method": "trace_replayBlockTransactions",
  "params": [
    "0xccb93d",
    [
      "trace"
    ]
  ],
  "id": 1,
  "jsonrpc": "2.0"
})
headers = {
  'Content-Type': 'application/json'
}

response = requests.request("POST", rpc_url, headers=headers, data=payload)

print(response.text)


end_time = time.time()
print(f'Time taken: {end_time-start_time:.2f} seconds')

vm_traces_data.to_csv('data/vm_traces.csv')

