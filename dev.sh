#!/bin/bash

case "$-" in
	*i*) ;;
	*)  echo
		echo "You can't run this as a script, please run:"
		echo source dev.sh
		echo
		exit 1
		;;
esac

if [ ! -e ./common.sh ]; then
	echo "ERROR: can't find required file (common.sh) - you need to change to the directory that dev.sh is in and source it from there"
	return 1
fi

# lots of functions defined in here
. ./common.sh

LOG_FILE='.forge-install.log'
rm -f $LOG_FILE
touch $LOG_FILE

# use && to chain operations that may fail
# if one fails, the chain stops
assert_have_python &&

assert_have_easy_install &&

install_virtualenv &&
make_dev_virtualenv_if_necessary &&
activate_dev_virtualenv &&

install_pip_if_necessary &&
install_dev_dependencies &&

# don't need to install the library as the wm- scripts locate it
# install_forge_library &&
put_wm_scripts_in_path &&


echo 'Forge environment ready, entering command line interface.' &&
echo

undefine_functions

rm -f $LOG_FILE
