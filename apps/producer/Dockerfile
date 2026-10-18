FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir kafka-python==2.2.15

COPY producer.py .

RUN useradd --create-home appuser
USER appuser

CMD ["python", "-u", "producer.py"]
