'Entry points for the WebMynd build tools'
import logging
import json
import shutil

import argparse
import os
import time


import webmynd
from webmynd import defaults, build_config, ForgeError
from webmynd.generate import Generate
from webmynd.remote import Remote, AuthenticationError
from webmynd.templates import Manager
from webmynd.android import runAndroid

LOG = None

class RunningInForgeRoot(Exception):
	pass

def _assert_outside_of_forge_root():
	if os.getcwd() == defaults.FORGE_ROOT:
		raise RunningInForgeRoot

def _warn_if_subdirectory_of_forge_root():
	if str(os.getcwd()).startswith(str(defaults.FORGE_ROOT)):
		# XXX: LOG hasn't been set up when this is called, would be good to do that earlier
		print
		print """WARNING: running webmynd commands in a subdirectory of the forge build tools, this is probably a bad idea - please do your app development in a folder outside of the build tools"""
		print

def with_error_handler(function):
	def decorated_with_handler(*args, **kwargs):
		try:
			_assert_outside_of_forge_root()
			_warn_if_subdirectory_of_forge_root()
			function(*args, **kwargs)
		except RunningInForgeRoot:
			# XXX: would use logging here, but there's no logging setup at this point - it gets setup
			# inside the command based on arguments
			# might be able to setup logging earlier on in this global handler?
			print
			print "ERROR: You're trying to run commands in the build tools directory, you need to move to another directory outside of this one first."
		except ForgeError as e:
			# thrown by us, expected
			# XXX: want to print this out, going to sort out logging here.
			pass
		except Exception as e:
			print "WHOOPS2"
			import traceback
			traceback.print_exc()
			LOG.debug("UNCAUGHT EXCEPTION: ", exc_info=True)
			LOG.error("Something went wrong that we didn't expect:");
			LOG.error(e);
			LOG.error("Please contact support@webmynd.com");

	return decorated_with_handler

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
	logging.basicConfig(level=log_level, format='[%(levelname)7s] %(message)s')
	LOG = logging.getLogger(__name__)
	LOG.info('WebMynd tools running at version %s' % webmynd.VERSION)

def add_general_options(parser):
	'Generic command-line arguments'
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	
def handle_general_options(args):
	'Parameterise our option based on common command-line arguments'
	setup_logging(args)

class CouldNotLocate(Exception):
	pass

def _check_for_dir(dirs, fail_msg):
	for directory in dirs:
		if (os.path.isdir(directory)):
			if directory.endswith('/'):
				return directory
			else:
				return directory+'/'
	else:
		raise CouldNotLocate(fail_msg)

def run():
	def not_chrome(text):
		if text == "chrome":
			msg = """

Currently it is not possible to launch a Chrome extension via this interface. The required steps are:

	1) Go to chrome:extensions in the Chrome browser
	2) Make sure "developer mode" is on (top right corner)')
	3) Use "Load unpacked extension" and browse to ./development/chrome"""
			raise argparse.ArgumentTypeError(msg)
		return text

	parser = argparse.ArgumentParser(prog='wm-run', description='Run a built dev app on a particular platform')
	parser.add_argument('-s', '--sdk', help='Path to the Android SDK')
	parser.add_argument('-j', '--jdk', help='Path to the Java JDK')
	parser.add_argument('-d', '--device', help='Android device id (to run apk on a specific device)')
	parser.add_argument('platform', type=not_chrome, choices=['android'])
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)

	if args.platform == 'android':
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

		try:
			sdk = _check_for_dir(possibleSdk, "No Android SDK found, please specify with the --sdk flag")
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
				"C:/Program Files/Java/jdk1.7.0/bin/",
				"/System/Library/Frameworks/JavaVM.framework/Versions/CurrentJDK/Commands"
			]
			if args.jdk:
				possibleJdk.insert(0, args.jdk)
			jdk = _check_for_dir(possibleJdk, "No Java JDK found, please specify with the --jdk flag")
			
			runAndroid(sdk, jdk, args.device)
		except CouldNotLocate as e:
			LOG.error(e)

def create():
	'Create a new development environment'
	parser = argparse.ArgumentParser(prog='wm-create', description='Initialises your development environment')
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

	manager = Manager(config)
	
	if os.path.exists(defaults.SRC_DIR):
		LOG.error('Source folder "%s" already exists, if you really want to create a new app you will need to remove it!' % defaults.SRC_DIR)
	else:
		name = raw_input('Enter app name: ')
		try:
			uuid = remote.create(name)
			remote.fetch_initial(uuid)
			LOG.info('App structure created. To proceed:')
			LOG.info('1) Put your code in the "%s" folder' % defaults.SRC_DIR)
			LOG.info('2) Run wm-dev-build to make a development build')
			LOG.info('3) Run wm-prod-build to make a production build')
		except AuthenticationError as e:
			LOG.error('Failed to login to forge: %s' % e.message)

def development_build():
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	
	parser = argparse.ArgumentParser(prog='wm-dev-build', description='Creates new local, unzipped development add-ons with your source and configuration')
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	if not os.path.isdir(defaults.SRC_DIR):
		LOG.error('Source folder "%s" does not exist - have you run wm-create yet?' % defaults.SRC_DIR)
		return 1
	
	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1
	manager = Manager(config)

	templates_dir = manager.templates_for_config(defaults.APP_CONFIG_FILE)
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
			tryAgain += 1
			shutil.copytree(templates_dir, 'development')
			break
		except Exception, e:
			if tryAgain == 5:
				raise
		
	generator = Generate(defaults.APP_CONFIG_FILE)
	generator.all('development', defaults.SRC_DIR)
	LOG.info("Development build created. Use wm-run to run your app.")

def production_build():
	'Trigger a new build'
	# TODO commonality between this and development_build
	parser = argparse.ArgumentParser(prog='wm-prod-build', description='Start a new production build and retrieve the packaged and unpackaged output')
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)

	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

	build_id = int(remote.build(development=False, template_only=False))
	
	LOG.info('fetching new WebMynd build')
	remote.fetch_packaged(build_id, to_dir='production')
	LOG.info("Production build created. Use wm-run to run your app.")
