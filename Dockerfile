FROM python:3.11-slim

# Optimize Python / pip behavior for container builds
ENV PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# System deps:
# - ffmpeg/libopus: Discord voice playback
# - nodejs: required by modern yt-dlp YouTube extraction (EJS challenges)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    ffmpeg \
    libopus0 \
    libffi8 \
    nodejs \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean \
 && node -v

WORKDIR /app

# Install Python deps first for better Docker layer caching
COPY requirements.txt ./
RUN pip install -r requirements.txt \
 && python -c "import yt_dlp, yt_dlp_ejs; print('yt-dlp', yt_dlp.version.__version__, 'ejs OK')"

# Application source
COPY . .

CMD ["python", "bot.py"]
