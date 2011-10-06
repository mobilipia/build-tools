#!/bin/bash

case "$-" in
	*i*) ;;
	*)  echo
		echo "You can't run this as a script, please run:"
		echo source go.sh
		echo
		exit 1
		;;
esac

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

check_for_folder () {
	if [ ! -e $1 ]
	then
		echo Cant find the $1 folder - you need to make sure you\'re running this script from the same folder that it\'s in
		failure
	fi
}

check_for_file () {
	if [ ! -e $1 ]
	then
		echo Cant find file: $1 - you need to make sure you\'re running this script from the same folder that it\'s in
		failure
	fi
}

python -V >> $LOG_FILE 2>&1
if [ $? -ne 0 ]
then
	echo 'Python not found.'
	echo 'You can download it from here: http://webmynd.com/forge/requirements/'
	failure 
fi

check_for_folder scripts
check_for_folder webmynd-dependencies
check_for_file scripts/activate

. ./scripts/activate
if [ $? -ne 0 ]
then
	echo 'The script to activate the virtual environment was there but something went wrong running it. You possibly need a fresh copy of the build tools.'
	failure
fi

rm -f $LOG_FILE

echo
echo Welcome to the Forge development environment!
echo
echo To get started, change to a fresh directory for your app, then run: wm-create
echo
