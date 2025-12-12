FROM python:3.10-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && \
    apt-get install -y docker.io && \
    pip install flask python-dotenv requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY scheduler.py prompts.py ./

RUN pip install -r requirements.txt

CMD ["python", "scheduler.py"]
