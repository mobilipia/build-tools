'Entry points for the WebMynd build tools'
import logging
import shutil

import argparse
import os
import time


import webmynd
from webmynd.config import Config
from webmynd import defaults
from webmynd.generate import Generate
from webmynd.remote import Remote
from webmynd.templates import Manager
from webmynd.android import runAndroid

LOG = None

def setup_logging(args):
	'Adjust logging parameters according to command line switches'
	global LOG
	if args.verbose and args.quiet:
		args.error('Cannot run in quiet and verbose mode at the same time')
	if args.verbose:
		log_level = logging.DEBUG
	elif args.quiet:
		log_level = logging.WARNING
	else:
		log_level = logging.INFO
	logging.basicConfig(level=log_level, format='[%(levelname)7s] %(asctime)s -- %(message)s')
	LOG = logging.getLogger(__name__)
	LOG.info('WebMynd tools running at version %s' % webmynd.VERSION)

def add_general_options(parser):
	'Generic command-line arguments'
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	
def handle_general_options(args):
	'Parameterise our option based on common command-line arguments'
	setup_logging(args)

def run():
	parser = argparse.ArgumentParser('Run a built dev app on a particular platform')
	parser.add_argument('-s', '--sdk', help='Path to the Android SDK')
	parser.add_argument('-j', '--jdk', help='Path to the Java JDK')
	parser.add_argument('-d', '--device', help='Android device id (to run apk on a specific device)')
	parser.add_argument('platform', choices=['android'])
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	if args.platform == 'android':
		sdk = ''
		# Some sensible places to look for the Android SDK
		possibleSdk = [
			"C:/Program Files (x86)/Android/android-sdk/",
			"C:/Program Files/Android/android-sdk/",
			"C:/Android/android-sdk/",
			"C:/Android/android-sdk-windows/",
			"C:/android-sdk-windows/"
		]
		if args.sdk:
			possibleSdk.insert(0, args.sdk)
		for curSdk in possibleSdk:
			if (os.path.isdir(curSdk)):
				if curSdk[-1:] == '/':
					sdk = curSdk
				else:
					sdk = curSdk+'/'
				break
		if sdk == '':
			raise Exception("No Android SDK found, please specify with the --sdk flag")
		# Some sensible places to look for the Java JDK
		possibleJdk = [
			"C:/Program Files (x86)/Java/jdk1.6.0_24/bin/",
			"C:/Program Files/Java/jdk1.6.0_24/bin/",
			"C:/Program Files (x86)/Java/jdk1.6.0_25/bin/",
			"C:/Program Files/Java/jdk1.6.0_25/bin/",
			"C:/Program Files (x86)/Java/jdk1.6.0_26/bin/",
			"C:/Program Files/Java/jdk1.6.0_26/bin/",
			"C:/Program Files (x86)/Java/jdk1.6.0_27/bin/",
			"C:/Program Files/Java/jdk1.6.0_27/bin/",
			"C:/Program Files (x86)/Java/jdk1.7.0/bin/",
			"C:/Program Files/Java/jdk1.7.0/bin/"
		]
		if args.jdk:
			possibleSdk.insert(0, args.jdk)
		for curJdk in possibleJdk:
			if (os.path.isdir(curJdk)):
				if curJdk[-1:] == '/':
					jdk = curJdk
				else:
					jdk = curJdk+'/'
				break
		if jdk == '':
			raise Exception("No Java JDK found, please specify with the --sdk flag")

		runAndroid(sdk, jdk, args.device)

def create():
	'Create a new development environment'
	parser = argparse.ArgumentParser('Initialises your development environment')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	config = Config()
	config.parse(args.config)
	
	remote = Remote(config)
	manager = Manager(config)
	
	if os.path.exists('user'):
		LOG.error('Folder "user" already exists, if you really want to create a new app you will need to remove it!')
	else:
		name = raw_input('Enter app name: ')
		uuid = remote.create(name)
		remote.fetch_initial(uuid)

def development_build():
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	
	parser = argparse.ArgumentParser('Creates new local, unzipped development add-ons with your source and configuration')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	if not os.path.isdir('user'):
		LOG.error('Folder "user" does not exist - have you run wm-create yet?')
		return 1
	
	config = Config()
	config.parse(args.config)
	remote = Remote(config)
	manager = Manager(config)

	templates_dir = manager.templates_for_config(config.app_config_file)
	if templates_dir:
		LOG.info('configuration is unchanged: using existing templates')
	else:
		LOG.info('configuration has changed: creating new templates')
		# configuration has changed: new template build!
		build_id = int(remote.build(development=True, template_only=True))
		# retrieve results of build
		templates_dir = manager.fetch_templates(build_id)
	
	shutil.rmtree('development', ignore_errors=True)
	# Windows often gives a permission error without a small wait
	tryAgain = 0
	while tryAgain < 5:
		time.sleep(tryAgain)
		try:
			tryAgain = tryAgain + 10
			shutil.copytree(templates_dir, 'development')
		except Exception, e:
			tryAgain = tryAgain - 9
			if tryAgain == 5:
				raise
		
	generator = Generate(config.app_config_file)
	generator.all('development', defaults.USER_DIR)

def production_build():
	'Trigger a new build'
	# TODO commonality between this and development_build
	parser = argparse.ArgumentParser('Start a new production build and retrieve the packaged and unpackaged output')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)

	config = Config()
	config.parse(args.config)
	remote = Remote(config)
	
	build_id = int(remote.build(development=False, template_only=False))
	
	LOG.info('fetching new WebMynd build')
	remote.fetch_packaged(build_id, to_dir='production')