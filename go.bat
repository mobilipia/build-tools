@echo off
python -V 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO nopython
ECHO Python found.

easy_install --help 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO noeasyinstall
ECHO easy_install found.

virtualenv --version 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO novirtualenv
ECHO virtualenv found.
:virtualenvinstalled

IF EXIST webmynd-environment GOTO virtualenvcreated
virtualenv --no-site-packages webmynd-environment
IF ERRORLEVEL 1 GOTO createvirtualenvfail
ECHO WebMynd virtual env created.

:virtualenvcreated
CALL webmynd-environment\Scripts\activate.bat
ECHO Entered WebMynd virtual env.

pip --version 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO nopip
ECHO pip found.
:pipinstalled

ECHO Checking and installing requirements, this may take some time.
pip install -r requirements.txt 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO reqfail
ECHO Requirements found and installed.

IF EXIST WebMynd_Build_Tools.egg-info GOTO setupcomplete
python setup.py install 2>NUL 1>NUL
IF ERRORLEVEL 1 GOTO setupfail
ECHO WebMynd enviroment initialised.
:setupcomplete

ECHO WebMynd environment ready, entering command line interface.
GOTO success

:nopip
ECHO No pip, attempting install
easy_install pip
IF ERRORLEVEL 1 GOTO easyinstallfail
ECHO pip installed.
GOTO pipinstalled

:novirtualenv
ECHO No virtualenv, attempting install
easy_install virtualenv
IF ERRORLEVEL 1 GOTO easyinstallfail
ECHO virtualenv installed.
GOTO virtualenvinstalled

:reqfail
ECHO.
ECHO Requirements install failed.
GOTO failure

:reqfail
ECHO.
ECHO WebMynd setup failed
GOTO failure

:easyinstallfail
ECHO.
ECHO Failed to install Python package using easy_install.
GOTO failure

:createvirtualenvfail
ECHO.
ECHO Creating the virtual environment for Python failed.
GOTO failure

:nopython
ECHO.
ECHO Python not found, make sure Python is installed and in your path.
ECHO you can download it here: http://www.python.org/getit/
GOTO failure

:noeasyinstall
ECHO.
ECHO Easy Install not found.
ECHO you can download it here: http://pypi.python.org/pypi/setuptools
GOTO failure

:failure
ECHO.
ECHO Something went wrong! Check the output above for more details and see the documentation for common troubleshooting issues.
ECHO.
PAUSE
EXIT

:success
ECHO.
cmd /k