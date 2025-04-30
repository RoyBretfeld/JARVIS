@echo off
echo Going to project directory...
cd /D "D:\_____RH-IT\JARVIS"
if %errorlevel% neq 0 (
    echo Failed to change directory to project root. Exiting.
    pause
    exit /b %errorlevel%
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate venv. Exiting.
    pause
    exit /b %errorlevel%
)

echo Changing directory to src/scraping...
cd src\scraping
if %errorlevel% neq 0 (
    echo Failed to change directory to src/scraping. Exiting.
    pause
    exit /b %errorlevel%
)

echo Finding spiders...
for /f "tokens=*" %%a in ('scrapy list') do (
    echo Running spider: %%a ...
    scrapy crawl %%a
    if %errorlevel% neq 0 (
        echo Failed to run spider: %%a
        rem Decide if you want to stop on error or continue with the next spider
        rem pause
        rem exit /b %errorlevel%
    ) else (
        echo Spider %%a finished.
    )
)

echo All spiders finished. Deactivating venv...
call venv\Scripts\deactivate.bat
echo Done.
rem Optional: pause am Ende entfernen, wenn das Fenster sich sofort schließen soll
rem pause
exit /b 0
