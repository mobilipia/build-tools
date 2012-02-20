@echo off
setlocal enableextensions enabledelayedexpansion

SET LOG_FILE=forge-install.log
IF EXIST %LOG_FILE% del %LOG_FILE%

rem look for python27 first
if EXIST "C:\Python27\python.exe" (
	set "PYTHONINSTALL=C:\Python27"
	goto foundpython
)

if EXIST "C:\Program Files\Python27\python.exe" (
	set "PYTHONINSTALL=C:\Program Files\Python27"
	goto foundpython
)

if EXIST "C:\Program Files (x86)\Python27\python.exe" (
	set "PYTHONINSTALL=C:\Program Files (x86)\Python27"
	goto foundpython
)

rem then look for python26
if EXIST "C:\Python26\python.exe" (
	set "PYTHONINSTALL=C:\Python26"
	goto foundpython
)

if EXIST "C:\Program Files\Python26\python.exe" (
	set "PYTHONINSTALL=C:\Program Files\Python26"
	goto foundpython
)

if EXIST "C:\Program Files (x86)\Python26\python.exe" (
	set "PYTHONINSTALL=C:\Program Files (x86)\Python26"
	goto foundpython
)

:foundpython

rem if we found a python installation, let's put it in the path
rem if we didn't find one we'll continue, hoping that python is in the path

if "!PYTHONINSTALL!" NEQ "" (
	SET PATH=!PATH!;!PYTHONINSTALL!
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
ECHO Python not found, make sure Python is in your PATH, or installed in any of:
ECHO.

ECHO C:\Python27
ECHO C:\Program Files\Python27
ECHO C:\Program Files (x86)\Python27

ECHO C:\Python26
ECHO C:\Program Files\Python26
ECHO C:\Program Files (x86)\Python26

ECHO.
ECHO you can download it here: https://trigger.io/forge/requirements/#Python
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

rem if the first argument is not empty
IF NOT %1.==. (
	rem then this script is effectively being "sourced", skip launching a subshell
	GOTO end
)

ECHO.
ECHO Welcome to the Forge development environment!
ECHO.
ECHO To get started, change to a fresh directory for your app, then run: forge create
ECHO.
cmd /k
:end
