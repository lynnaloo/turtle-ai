FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY scheduler.py prompts.py ./

CMD ["python", "scheduler.py"]
