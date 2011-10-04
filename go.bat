@echo off
set LOG_FILE=webmynd-install.log
IF EXIST %LOG_FILE% del %LOG_FILE%

rem
rem LOCATE PYTHON AND STICK IT IN OUR PATH (the python installer doesn't do that...)
rem
SET WINCURVERKEY=HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion
REG QUERY "%WINCURVERKEY%" /v "ProgramFilesDir (x86)" >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  SET WIN64=1
) else (
  SET WIN64=0
)

if "%WIN64%" EQU "1" (
  SET PYTHONKEY=HKLM\SOFTWARE\Wow6432Node\Python\PythonCore
) else (
  SET PYTHONKEY=HKLM\SOFTWARE\Python\PythonCore
)

SET PYTHONVERSION=
SET PYTHONINSTALL=

if "%PYTHONVERSION%" EQU "" (
  REG QUERY "%PYTHONKEY%\2.7\InstallPath" /ve >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    SET PYTHONVERSION=2.7
  )
)

if "%PYTHONVERSION%" EQU "" (
  REG QUERY "%PYTHONKEY%\2.6\InstallPath" /ve >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    SET PYTHONVERSION=2.6
  )
)

if "%PYTHONVERSION%" EQU "" (
  REG QUERY "%PYTHONKEY%\2.5\InstallPath" /ve >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    SET PYTHONVERSION=2.5
  )
)

if "%PYTHONVERSION%" EQU "" (
  REG QUERY "%PYTHONKEY%\2.4\InstallPath" /ve >nul 2>nul
  if %ERRORLEVEL% EQU 0 (
    SET PYTHONVERSION=2.4
  )
)

if "%PYTHONVERSION%" NEQ "" (
  FOR /F "tokens=3* skip=1 delims=	 " %%A IN ('REG QUERY "%PYTHONKEY%\%PYTHONVERSION%\InstallPath" /ve') DO SET "PYTHONINSTALL=%%A"
)

if "%PYTHONINSTALL%" NEQ "" (
  SET "PATH=%PATH%;%PYTHONINSTALL%"
)

rem
rem END LOCATE PYTHON
rem

python -V 1>%LOG_FILE% 2>&1
IF ERRORLEVEL 1 GOTO nopython

SET FORGE_ROOT=%CD%

CALL scripts\activate.bat

GOTO success

:nopython
ECHO.
ECHO Python not found, make sure Python is installed and in your path.
ECHO you can download it here: http://www.python.org/getit/
GOTO failure

:failure
ECHO.
ECHO Something went wrong! Check the output above for more details and see the documentation for common troubleshooting issues.
ECHO.
PAUSE
EXIT
rem 
:success
ECHO.

del %LOG_FILE%

cmd /k