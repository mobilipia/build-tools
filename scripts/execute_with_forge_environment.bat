@echo off
rem execute_with_forge_environment
rem ==============================
rem
rem used to aid automatic testing of the forge environment
rem
rem changes directory to the build tools, activates the environment (using
rem go.bat), and then runs the arguments to this script as a command


SET TOOLS_DIR=%~dp0\..
SET ORIG_DIR=%CD%

cd "%TOOLS_DIR%"
call go.bat dont launch shell
cd "%ORIG_DIR%"

%*