#!/bin/bash

LOG_FILE='.webmynd-install.log'
rm -f $LOG_FILE

failure () {
	echo
	echo 'START LOG OUTPUT'
	cat $LOG_FILE
	echo 'END LOG OUTPUT'
	echo
	echo 'Something went wrong! Check the output above for more details and see the documentation for common troubleshooting issues.'
	exit
}

python -V >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'Python not found.'
	failure 
fi
echo 'python found.'

easy_install --help  >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'easy_install not found.'
	failure 
fi
echo 'easy_install found.'

virtualenv --version  >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'No virtualenv, attempting install.'
	easy_install virtualenv
	if [ $? -ne 0 ]
	then
		echo
		echo 'Failed to install python package using easy_install.'
		failure
	fi
	echo 'virtualenv installed.'
fi
echo 'virtualenv found.'

if [ ! -e 'webmynd-environment' ]
then
	virtualenv --no-site-packages webmynd-environment
	if [ $? -ne 0 ]
	then
		echo
		echo 'Creating the virtual environment for python failed.'
		failure
	fi
	echo 'WebMynd virtual environment created.'
fi

. ./webmynd-environment/bin/activate

if [ $? -ne 0 ]; then
	rm -rf ./webmynd-environment
	echo
	echo 'Your virtual environment appears to be broken; please re-run this script to fix it!'
	exit
else
	echo 'Entered WebMynd virtual env.'
fi

pip --version  >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'No pip, attempting install.'
	easy_install pip
	if [ $? -ne 0 ]
	then
		echo
		echo 'Failed to install python package using easy_install.'
		failure
	fi
	echo 'pip installed.'
fi
echo 'pip found.'

echo 'Checking and installing requirements, this may take some time.'
pip install -r requirements.txt >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'Requirements install failed.'
	failure 
fi
echo 'Requirements found and installed.'

python setup.py install >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'WebMynd setup failed.'
	failure 
fi
echo 'WebMynd tools installed.'

echo 'WebMynd environment ready, entering command line interface.'
echo

rm $LOG_FILE

bash --norc
