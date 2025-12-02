@echo off
cd /d "%~dp0"

:: IMPOSTA LA CHIAVE QUI DIRETTAMENTE (Sostituisci la scritta sotto)
set GOOGLE_API_KEY=AIzaSyB3Tfm5y7cRiqN3rO_hLEO0ijx1faYDZR0

echo ---------------------------------------------------
echo  AVVIO SISTEMA TRIAGE (Backend + Frontend)
echo ---------------------------------------------------

:: Avvia il Cervello (Backend) in una nuova finestra
start "CERVELLO (Backend)" cmd /k "set GOOGLE_API_KEY=%GOOGLE_API_KEY% && .\venv\Scripts\activate && python main.py"

:: Aspetta 5 secondi che il cervello si svegli
timeout /t 5

:: Avvia la Faccia (Frontend) in una nuova finestra
start "FACCIA (Frontend)" cmd /k ".\venv\Scripts\activate && streamlit run frontend.py"