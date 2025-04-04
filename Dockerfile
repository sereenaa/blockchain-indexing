# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    unixodbc-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install any needed packages specified in requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# # Copy the shell script into the container
# COPY run_scripts.sh /app/run_scripts.sh

# # Make the shell script executable
# RUN chmod +x /app/run_scripts.sh

# Make port 80 available to the world outside this container
EXPOSE 80

# Run the shell script when the container launches
# CMD ["/app/run_scripts.sh"]

# Run the specified Python script with the given arguments when the container launches
# python, main.py, run_strategy, start_block, end_block, batch_size, rpc_number
# DONT FORGET TO CHANGE THE RPC NUMBER
CMD ["python", "main.py", "historical", "71675328", "72675328", "150", "1"]
