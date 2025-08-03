# Use smallest official Python Alpine image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

## Install system dependencies
RUN apt-get update && apt-get install -y build-essential git libgl1 libglib2.0-0

# Set work directory
WORKDIR /app

# Copy files
COPY . /app
COPY requirements.txt .

# Install dependencies

# for better caching

RUN pip install --no-cache-dir -r torch_requirements.txt

RUN pip install --no-cache-dir -r requirements.txt


# Expose port
EXPOSE 2500

# Run the FastAPI server
CMD ["uvicorn", "backend_main:app", "--host", "0.0.0.0", "--port", "2500"]
