@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0backend"

echo ===================================================
echo   3D Chromatin Structure Project - Starting...
echo ===================================================

REM --- التحقق من وجود الـ virtual environment (.env) جوا backend ---
if not exist ".env\Scripts\python.exe" (
    echo [ERROR] البيئة الافتراضية .env مش موجودة جوا مجلد backend!
    pause
    exit /b 1
)

REM --- التحقق من البورت 8000 مش مأخوذ ---
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [WARNING] البورت 8000 مستخدم من برنامج تاني.
    pause
    exit /b 1
)

REM --- التحقق من خدمة Redis/Memurai وتشغيلها لو موقوفة ---
echo [1/5] Checking Redis/Memurai service...
set REDIS_SERVICE=
sc query Memurai >nul 2>&1
if !errorlevel! equ 0 set REDIS_SERVICE=Memurai
if not defined REDIS_SERVICE (
    sc query Redis >nul 2>&1
    if !errorlevel! equ 0 set REDIS_SERVICE=Redis
)
if not defined REDIS_SERVICE (
    echo [ERROR] ما لقيت خدمة Redis ولا Memurai منصّبة.
    echo https://www.memurai.com/get-memurai
    pause
    exit /b 1
)
sc query !REDIS_SERVICE! | findstr "RUNNING" >nul
if !errorlevel!==0 (
    echo       !REDIS_SERVICE! service is already running.
) else (
    net start !REDIS_SERVICE!
    if !errorlevel! neq 0 (
        echo [ERROR] فشل تشغيل خدمة !REDIS_SERVICE!.
        pause
        exit /b 1
    )
)

REM --- تشغيل Celery Worker مخفي تماماً + حفظ PID ---
echo [2/5] Starting Celery worker (hidden)...
for /f "usebackq" %%P in (`powershell -NoProfile -Command ^
    "(Start-Process -FilePath '.env\Scripts\python.exe' -ArgumentList '-m celery -A core worker -l info --pool=solo' -WindowStyle Hidden -PassThru).Id"`) do set CELERY_PID=%%P
echo !CELERY_PID! > "%~dp0.celery_pid.tmp"
timeout /t 3 /nobreak >nul

REM --- تشغيل Watchdog مخفي تماماً + حفظ PID ---
echo [2.5/5] Starting background watchdog (hidden)...
for /f "usebackq" %%P in (`powershell -NoProfile -Command ^
    "(Start-Process -FilePath 'cmd.exe' -ArgumentList '/c cd /d %~dp0backend ^&^& :loop ^& .env\Scripts\python.exe manage.py watchdog_check ^& timeout /t 60 /nobreak ^>nul ^& goto loop' -WindowStyle Hidden -PassThru).Id"`) do set WATCHDOG_PID=%%P
echo !WATCHDOG_PID! >> "%~dp0.celery_pid.tmp"

REM --- تطبيق migrations ---
echo [3/5] Applying database migrations...
.env\Scripts\python.exe manage.py migrate
if %errorlevel% neq 0 (
    echo [ERROR] فشل الـ migrate.
    pause
    exit /b 1
)

REM --- جمع الـ static files ---
echo [4/5] Collecting static files...
.env\Scripts\python.exe manage.py collectstatic --noinput >nul

REM --- فتح المتصفح ---
echo [5/5] Opening browser...
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8000

echo ===================================================
echo   Server is running on http://127.0.0.1:8000
echo   لا تسكر هاد الشباك — سكره بيوقف السيرفر بالكامل.
echo ===================================================
.env\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8000 core.wsgi:application

REM --- عند إغلاق السيرفر، نضف العمليات المخفية بدقة عبر PID ---
echo Shutting down...
if exist "%~dp0.celery_pid.tmp" (
    for /f %%P in (%~dp0.celery_pid.tmp) do taskkill /PID %%P /T /F >nul 2>&1
    del "%~dp0.celery_pid.tmp"
)
pause