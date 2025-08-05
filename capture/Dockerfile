FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y docker.io && \
    apt-get install -y ffmpeg && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY capture_image.py ./

RUN mkdir -p images
RUN pip install -r requirements.txt

CMD ["python", "capture_image.py"]
