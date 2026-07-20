FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir httpx python-jose[cryptography] jinja2

# Copy application
COPY . .

# Expose port
EXPOSE 8102

# Run
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8102"]
