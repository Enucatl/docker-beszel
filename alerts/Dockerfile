FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY alerts/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --requirement /app/requirements.txt
COPY alerts/reconcile.py /app/reconcile.py

ENTRYPOINT ["python", "/app/reconcile.py"]
