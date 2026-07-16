FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies first (layer cache-friendly)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the existing SQLAlchemy models and supporting data modules
COPY src/data/ ./src/data/

# Copy the FastAPI application
COPY backend/app/ ./app/

# Tell db.py / demo.py that we are running inside Docker
ENV IN_DOCKER=true

# Expose the API port
EXPOSE 8052

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8052"]
