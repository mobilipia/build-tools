@echo off
set VIRTUAL_ENV=webmynd-environment

if defined _OLD_PYTHONPATH (
    set "PYTHONPATH=%_OLD_PYTHONPATH%"
)
if not defined PYTHONPATH (
    set PYTHONPATH=;
)
set _OLD_PYTHONPATH=%PYTHONPATH%
set PYTHONPATH=%CD%\webmynd-dependencies;%CD%;%PYTHONPATH%

if not defined PROMPT (
    set PROMPT=$P$G
)

if defined _OLD_VIRTUAL_PROMPT (
    set "PROMPT=%_OLD_VIRTUAL_PROMPT%"
)

set _OLD_VIRTUAL_PROMPT=%PROMPT%
set PROMPT=(%VIRTUAL_ENV%) %PROMPT%

if defined _OLD_VIRTUAL_PATH (
    set "PATH=%_OLD_VIRTUAL_PATH%"
    goto SKIPPATH
)
set _OLD_VIRTUAL_PATH=%PATH%

:SKIPPATH
set PATH=%CD%\scripts;%PATH%

:END
