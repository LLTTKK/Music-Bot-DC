# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# 優化環境變數
ENV PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# 系統相依套件（音訊播放所需）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
 && rm -rf /var/lib/apt/lists/* \
 && apt-get clean

WORKDIR /app

# 關鍵：先複製 requirements.txt
COPY requirements.txt ./

# 安裝依賴 - 這層只有在 requirements.txt 改變時才會重建
RUN pip install -r requirements.txt

# 複製應用程式代碼 - 這層在代碼改變時會重建，但不會重新安裝套件
COPY . .

# 健康檢查 (可選)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import discord; print('OK')" || exit 1

CMD ["python", "bot.py"]


