undefine_functions () {
	# unset -f just removes the functions used in this script

	# everyone needs python
	unset -f assert_have_python
	unset -f assert_user_have_python

	# dev requirements
	unset -f assert_have_easy_install
	unset -f install_virtualenv
	unset -f make_dev_virtualenv_if_necessary
	unset -f activate_dev_virtualenv
	unset -f remove_dev_virtualenv
	unset -f install_pip_if_necessary
	unset -f install_dev_dependencies
	unset -f install_forge_library

	# user requirements
	unset -f activate_user_virtualenv
	unset -f failure

	# asserts
	unset -f check_for_file
	unset -f check_for_folder

	# this
	unset -f undefine_functions
}


failure () {
	echo
	echo 'START LOG OUTPUT'
	cat $LOG_FILE
	echo 'END LOG OUTPUT'
	echo
	echo 'Something went wrong! Check the output above for more details and see the documentation for common troubleshooting issues.'
}

assert_user_have_python () {
	python -V >> $LOG_FILE 2>&1
	if [ $? -ne 0 ]
	then
		echo 'Python not found.'
		echo 'You can download it from here: https://webmynd.com/forge/requirements/'
		failure
		return 1
	fi
}

assert_have_python () {
	python -V >> $LOG_FILE 2>&1
	if [ $? -ne 0 ]
	then
		echo 'Python not found.'
		echo 'You can download it from here: https://webmynd.com/forge/requirements/'
		failure
		return 1
	fi
	echo 'python found.'
}

assert_have_easy_install () {
	easy_install --help  >> $LOG_FILE 2>&1
	if [ $? -ne 0 ]
	then
		echo 'easy_install not found.'
		failure
		return 1
	fi
	echo 'easy_install found.'
}

install_virtualenv () {
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
			return 1
		fi
		echo 'virtualenv installed.'
	fi
	echo 'virtualenv found.'
}

make_dev_virtualenv_if_necessary () {
	if [ ! -e 'forge-environment' ]
	then
		virtualenv --no-site-packages forge-environment
		if [ $? -ne 0 ]
		then
			echo
			echo 'Creating the virtual environment for python failed.'
			failure
			return 1
		fi
		echo 'Forge virtual environment created.'
	fi
}

activate_dev_virtualenv () {
	. ./forge-environment/bin/activate
	if [ $? -ne 0 ]; then
		remove_dev_virtualenv
	else
		echo 'Entered Forge virtual env.'
	fi
}

remove_dev_virtualenv () {
	rm -rf ./forge-environment
	echo
	echo 'Your virtual environment appears to be broken; please re-run this script to fix it!'
	failure
	return 1
}

activate_user_virtualenv () {
	. ./scripts/activate
}

install_pip_if_necessary () {
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
			return 1
		fi
		echo 'pip installed.'
	fi
	echo 'pip found.'
}

install_dev_dependencies () {
	echo 'Checking and installing requirements, this may take some time.'
	pip install -r requirements.txt >> $LOG_FILE 2>&1
	if [ $? -ne 0 ]
	then
		echo 'Requirements install failed.'
		failure 
	fi
	echo 'Requirements found and installed.'
}

install_forge_library () {
	python setup.py install >> $LOG_FILE 2>&1
	if [ $? -ne 0 ]
	then
		echo 'Forge setup failed.'
		failure 
	fi
	echo 'Forge tools installed.'
}

put_wm_scripts_in_path () {
	export PATH="`pwd`"/scripts:$PATH
}

check_for_folder () {
	if [ ! -e $1 ]
	then
		echo Cant find the $1 folder - you need to make sure you\'re running this script from the same folder that it\'s in
		failure
		return 1
	fi
}

check_for_file () {
	if [ ! -e $1 ]
	then
		echo Cant find file: $1 - you need to make sure you\'re running this script from the same folder that it\'s in
		failure
		return 1
	fi
}

check_for_folder scripts &&
check_for_folder forge-dependencies &&
check_for_file scripts/activate
