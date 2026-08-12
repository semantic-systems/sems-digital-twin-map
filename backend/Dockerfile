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

# --proxy-headers/--forwarded-allow-ips: honour X-Forwarded-Proto from the nginx
# container in front of us, so redirects this app issues keep the browser's
# https scheme. Without it uvicorn only trusts 127.0.0.1 and the header from
# another container is ignored, making every redirect an http:// one. The "*" is
# safe here because the app is only reachable through that proxy on the internal
# compose network -- it is never published to the host.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8052", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
