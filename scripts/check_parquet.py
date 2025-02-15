import boto3
import pandas as pd
import io

def check_parquet_file_in_s3(bucket_name, s3_key):
    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Download the Parquet file from S3
        response = s3.get_object(Bucket=bucket_name, Key=s3_key)
        parquet_content = response['Body'].read()

        # Read the Parquet file into a pandas DataFrame
        buffer = io.BytesIO(parquet_content)
        df = pd.read_parquet(buffer)

        # Display basic information about the DataFrame
        print(f"Parquet file contents for {s3_key}:")
        print(f"Shape: {df.shape}")
        print("\nColumns:")
        print(df.columns.tolist())
        print("\nData types:")
        print(df.dtypes)
        print("\nEntire dataframe:")
        print(df)

        # Optionally, you can perform more specific checks or analysis here

    except Exception as e:
        print(f"Error reading Parquet file: {e}")

# Usage example
bucket_name = 'arbitrum-opcodes'
s3_key = 'raw_opcodes_dev/61190585_61190594.parquet'

check_parquet_file_in_s3(bucket_name, s3_key)