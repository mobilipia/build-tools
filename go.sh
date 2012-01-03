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

if [ ! -e ./common.sh ]; then
	echo "ERROR: can't find required file (common.sh) - you need to change to the directory that go.sh is in and source it from there"
	return 1
fi

# lots of functions defined in here
. ./common.sh

LOG_FILE='.forge-install.log'
rm -f $LOG_FILE
touch $LOG_FILE

assert_user_have_python &&

activate_user_virtualenv &&
put_wm_scripts_in_path &&

(
	echo
	echo Welcome to the Forge development environment!
	echo
	echo To get started, change to a fresh directory for your app, then run: wm-create
	echo
)

undefine_functions

rm -f $LOG_FILE
