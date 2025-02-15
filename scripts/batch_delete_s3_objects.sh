#!/bin/bash

BUCKET_NAME="arbitrum-opcodes"
PREFIX="raw_opcodes/"
THRESHOLD=60141194
BATCH_SIZE=1000

# Function to delete a batch of objects
delete_batch() {
    local json_input=$1
    aws s3api delete-objects --bucket "$BUCKET_NAME" --delete "$json_input"
}

# Initialize an empty array to store objects to delete
declare -a objects_to_delete

# Counter for the current batch
count=0

# Process each .parquet file
aws s3 ls "s3://$BUCKET_NAME/$PREFIX" --recursive | grep '\.parquet$' | awk '{print $NF}' | while read -r filename; do
    # Extract the number from the filename
    number=$(basename "$filename" .parquet)
    
    # Check if the extracted number is actually a number
    if [[ "$number" =~ ^[0-9]+$ ]]; then
        # Check if the number is less than the threshold
        if [ "$number" -lt $THRESHOLD ]; then
            # Add object to the array
            objects_to_delete+=("{\"Key\":\"$filename\"}")
            echo "Added to delete list: $filename" # Debug output
            ((count++))

            # If we've reached the batch size, delete the batch
            if [ $count -eq $BATCH_SIZE ]; then
                echo "Deleting batch of $BATCH_SIZE files" # Debug output
                json_input=$(printf '{"Objects":[%s],"Quiet":true}' "$(IFS=,; echo "${objects_to_delete[*]}")")
                delete_batch "$json_input"
                
                # Reset the array and counter
                objects_to_delete=()
                count=0
            fi
        else
            echo "Skipping file above threshold: $filename" # Debug output
        fi
    else
        echo "Skipping non-numeric filename: $filename"
    fi
done

# Print the size of objects_to_delete 
#TODO: why is this 0 even if we have <1000 objects to delete?
echo "Current size of objects_to_delete: ${#objects_to_delete[@]}"

# Delete any remaining objects in the last batch
if [ ${#objects_to_delete[@]} -gt 0 ]; then
    json_input=$(printf '{"Objects":[%s],"Quiet":true}' "$(IFS=,; echo "${objects_to_delete[*]}")")
    delete_batch "$json_input"
fi