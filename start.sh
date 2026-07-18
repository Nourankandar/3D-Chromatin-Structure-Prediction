#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==================================================="
echo "  3D Chromatin Structure Project - Starting..."
echo "==================================================="

# --- التحقق من الـ venv ---
if [ ! -f "venv/bin/python" ]; then
    echo "[ERROR] venv مش موجودة! تأكد إنه مجلد venv موجود جوا المشروع."
    read -p "اضغط Enter للخروج..."
    exit 1
fi

# --- التحقق من البورت 8000 ---
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "[WARNING] البورت 8000 مستخدم من برنامج تاني."
    read -p "اضغط Enter للخروج..."
    exit 1
fi

# --- تشغيل Redis ---
echo "[1/5] Starting Redis..."
if command -v redis-server >/dev/null 2>&1; then
    redis-server --daemonize yes --port 6379
    sleep 2
else
    echo "[ERROR] redis-server مش مثبت أو مش موجود بالـ PATH."
    exit 1
fi

if ! redis-cli ping >/dev/null 2>&1; then
    echo "[ERROR] Redis ما اشتغل."
    exit 1
fi
echo "      Redis is running."

# --- تشغيل Celery ---
echo "[2/5] Starting Celery worker..."
venv/bin/python -m celery -A backend.core worker -l info --detach --pidfile=celery.pid
sleep 3

# --- migrations ---
echo "[3/5] Applying database migrations..."
venv/bin/python manage.py migrate

# --- static files ---
echo "[4/5] Collecting static files..."
venv/bin/python manage.py collectstatic --noinput

# --- فتح المتصفح ---
echo "[5/5] Opening browser..."
sleep 1
if command -v xdg-open >/dev/null 2>&1; then
    xdg-open http://127.0.0.1:8000 &   # Linux
elif command -v open >/dev/null 2>&1; then
    open http://127.0.0.1:8000 &       # macOS
fi

echo "==================================================="
echo "  Server running on http://127.0.0.1:8000"
echo "  اضغط Ctrl+C لإيقاف السيرفر."
echo "==================================================="

# --- تنظيف عند الإيقاف ---
cleanup() {
    echo "Shutting down..."
    kill $(cat celery.pid) 2>/dev/null
    rm -f celery.pid
    redis-cli shutdown 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

venv/bin/python -m waitress --host=127.0.0.1 --port=8000 backend.core.wsgi:application