# Use a base image with Python
FROM python:3.11.8-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
RUN pip install bitsandbytes
RUN pip install 'accelerate>=0.26.0'
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Expose the port on which the Flask app runs
EXPOSE 5000

# Command to run the Flask app
CMD ["python", "app.py"]
