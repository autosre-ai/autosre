FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client

COPY main.py .

EXPOSE 8080 8081

CMD ["python", "main.py"]
