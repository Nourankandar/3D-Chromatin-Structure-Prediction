FROM python:3.12-slim

# استخدام صورة PyTorch الرسمية الجاهزة (تحتوي على Python 3.12 و PyTorch)
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

# تثبيت حزم النظام الخاصة بالجينوم و pysam
RUN apt-get update && apt-get install -y \
    samtools \
    minimap2 \
    build-essential \
    curl \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# نسخ requirements وتثبيتها
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY backend/ /app/backend/
COPY ai_engine/ /app/ai_engine/

WORKDIR /app/backend

ENV DJANGO_SETTINGS_MODULE=core.settings
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]