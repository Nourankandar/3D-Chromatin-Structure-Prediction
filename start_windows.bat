@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ===================================================
echo   3D Chromatin Structure Project - Starting...
echo ===================================================

REM --- التحقق من وجود الـ venv ---
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] venv مش موجودة! تأكد إنه مجلد venv موجود جوا المشروع.
    pause
    exit /b 1
)

REM --- التحقق من البورت 8000 مش مأخوذ ---
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [WARNING] البورت 8000 مستخدم من برنامج تاني.
    echo تأكد إنه ما في نسخة تانية شغالة من البرنامج.
    pause
    exit /b 1
)

REM --- تشغيل Redis ---
echo [1/5] Starting Redis...
if exist "redis\redis-server.exe" (
    start "Redis Server" /min redis\redis-server.exe redis\redis.windows.conf
    timeout /t 3 /nobreak >nul
) else (
    echo [ERROR] redis-server.exe مش موجود بمجلد redis\
    pause
    exit /b 1
)

REM --- التحقق إنه Redis اشتغل فعلاً ---
timeout /t 2 /nobreak >nul
tasklist /FI "IMAGENAME eq redis-server.exe" 2>NUL | find /I /N "redis-server.exe">NUL
if %errorlevel% neq 0 (
    echo [ERROR] Redis ما اشتغل. تأكد من الملفات جوا مجلد redis\
    pause
    exit /b 1
)
echo       Redis is running.

REM --- تشغيل Celery Worker ---
echo [2/5] Starting Celery worker...
start "Celery Worker" /min venv\Scripts\python.exe -m celery -A backend.core worker -l info --pool=solo
timeout /t 3 /nobreak >nul

REM --- تطبيق migrations ---
echo [3/5] Applying database migrations...
venv\Scripts\python.exe manage.py migrate
if %errorlevel% neq 0 (
    echo [ERROR] فشل الـ migrate. راجع الرسالة فوق.
    pause
    exit /b 1
)

REM --- جمع الـ static files ---
echo [4/5] Collecting static files...
venv\Scripts\python.exe manage.py collectstatic --noinput >nul

REM --- فتح المتصفح ---
echo [5/5] Opening browser...
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000

REM --- تشغيل السيرفر (هاد بيضل شغال بالفورجراوند) ---
echo ===================================================
echo   Server is running on http://127.0.0.1:8000
echo   لا تسكر هاد الشباك — سكره بيوقف السيرفر بالكامل.
echo ===================================================
venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8000 backend.core.wsgi:application

REM --- عند إغلاق السيرفر، نضف العمليات ---
echo Shutting down...
taskkill /FI "WINDOWTITLE eq Celery Worker*" /F >nul 2>&1
taskkill /IM redis-server.exe /F >nul 2>&1
pause