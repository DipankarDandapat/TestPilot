FROM python:3.11-slim

WORKDIR /app

# Install system deps for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (build context = project root)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source only
COPY backend/ .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
