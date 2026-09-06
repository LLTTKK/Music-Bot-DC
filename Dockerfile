FROM python:3.11-slim

# Optimize Python / pip behavior for container builds
ENV PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# System deps for Discord voice playback
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libopus0 \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean

WORKDIR /app

# Install Python deps first for better Docker layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application source
COPY . .

CMD ["python", "bot.py"]
