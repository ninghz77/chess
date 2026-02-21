FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer if pyproject.toml unchanged)
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" websockets jinja2 python-multipart

# Copy source and install the package itself
COPY . .
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8080

CMD uvicorn api.main:app --host 0.0.0.0 --port 8080
