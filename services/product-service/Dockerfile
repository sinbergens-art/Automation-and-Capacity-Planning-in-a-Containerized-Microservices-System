FROM python:3.11-slim
 
WORKDIR /app
 
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*
 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
COPY main.py .
 
EXPOSE 8000
 
HEALTHCHECK --interval=15s --timeout=5s --retries=4 \
  CMD curl -fsS http://localhost:8000/health || exit 1
 
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
 