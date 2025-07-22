@echo off
echo 🚀 Starting AI-CBT Platform...
echo ==================================

REM Check if virtual environment exists
if not exist "venv" (
    echo ⚠️  Virtual environment not found. Creating one...
    python -m venv venv
)

REM Activate virtual environment
echo 📦 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Change to src directory
cd src

echo ==================================
echo 🌐 Starting Services...
echo ==================================

REM Start API service
echo 🔧 Starting API Service (Port 5001)...
start "AI-CBT API Service" python app_api.py

REM Wait a moment
timeout /t 3 /nobreak > nul

REM Start Education service
echo 🎓 Starting Education Portal (Port 5002)...
start "AI-CBT Education Portal" python education_app.py

echo ==================================
echo ✅ AI-CBT Platform is now running!
echo ==================================
echo 🌐 Main API Platform: http://localhost:5001/
echo 📖 API Documentation: http://localhost:5001/api/v1/docs
echo 🔧 Interactive Dashboard: http://localhost:5001/api-dashboard
echo 🎓 Education Portal: http://localhost:5002/
echo 👨‍💼 Admin Panel: http://localhost:5002/admin
echo ==================================
echo Close the command windows to stop the services
pause
