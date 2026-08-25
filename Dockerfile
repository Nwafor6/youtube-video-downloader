FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
# DEBIAN_FRONTEND=noninteractive prevents interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*


# Install uv (fast Python package installer)
RUN pip install uv

# Copy pyproject.toml and optionally poetry.lock if present
COPY pyproject.toml ./
COPY poetry.lock* ./

# Install dependencies using uv
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt


# Copy project
COPY . .

# Run uvicorn with multiple workers to use all available CPU cores

CMD ["uvicorn", "main:app", \
    "--host", "0.0.0.0", \
    "--port", "8000", \
    "--workers", "4", \
    "--ws-max-size", "10485760"]
