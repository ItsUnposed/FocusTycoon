@echo off
setlocal enabledelayedexpansion
REM Startet Focus Tycoon (Python/Pygame-Version).
REM Beim ersten Start werden fehlende Abhaengigkeiten (pygame) automatisch installiert.

cd /d "%~dp0"

REM Konsole auf UTF-8, damit deutsche Umlaute in der Demo-Ausgabe stimmen.
chcp 65001 >nul

REM Ein funktionierendes Python suchen. Wichtig: der WindowsApps-Platzhalter
REM ("...\WindowsApps\python.exe") steht oft im PATH, laesst sich aber nicht
REM ausfuehren - deshalb pruefen wir gezielt echte Installationen zuerst.
REM PYCMD = ausfuehrbares Programm, PYARG = optionales Argument (z. B. -3 fuer den Launcher).
set "PYCMD="
set "PYARG="

REM 1) Nutzer-Shim (hat hier bereits pygame installiert).
if exist "%LOCALAPPDATA%\Python\bin\python.exe" set "PYCMD=%LOCALAPPDATA%\Python\bin\python.exe"

REM 2) Sonst die konkrete pythoncore-Installation (neueste gefundene).
if not defined PYCMD (
    for /f "delims=" %%P in ('dir /b /s "%LOCALAPPDATA%\Python\pythoncore-*\python.exe" 2^>nul') do set "PYCMD=%%P"
)

REM 3) Sonst der Python-Launcher.
if not defined PYCMD (
    py -3 --version >nul 2>nul && ( set "PYCMD=py" & set "PYARG=-3" )
)

REM 4) Sonst python aus dem PATH - aber nur, wenn es wirklich startet
REM    (der WindowsApps-Platzhalter tut das nicht und faellt hier durch).
if not defined PYCMD (
    python --version >nul 2>nul && set "PYCMD=python"
)

if not defined PYCMD (
    echo Kein funktionierendes Python 3 gefunden.
    echo Bitte Python 3 von https://www.python.org/downloads/ installieren
    echo und beim Setup "Add Python to PATH" anhaken.
    pause
    exit /b 1
)

echo Verwende Python: "%PYCMD%" %PYARG%

REM pygame vorhanden? Wenn nicht, Abhaengigkeiten installieren.
"%PYCMD%" %PYARG% -c "import pygame" >nul 2>nul
if errorlevel 1 (
    echo Installiere Abhaengigkeiten ^(einmalig^) ...
    "%PYCMD%" %PYARG% -m pip install -r requirements.txt
)

"%PYCMD%" %PYARG% run.py %*
if errorlevel 1 pause
endlocal
