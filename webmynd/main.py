'Entry points for the WebMynd build tools'
import logging
import codecs
import json
import shutil
import sys

import argparse
import os
import time

from subprocess import Popen
from os import path, devnull

import webmynd
from webmynd import defaults, build_config, ForgeError
from webmynd.generate import Generate
from webmynd.remote import Remote
from webmynd.templates import Manager
from webmynd.android import check_for_android_sdk, CouldNotLocate, runAndroid
from webmynd.ios import IOSRunner
from cuddlefish.runner import run_app

LOG = None

class RunningInForgeRoot(Exception):
	pass

def _assert_outside_of_forge_root():
	if os.getcwd() == defaults.FORGE_ROOT:
		raise RunningInForgeRoot

def _assert_not_in_subdirectory_of_forge_root():
	cwd = str(os.getcwd())
	if cwd.startswith(defaults.FORGE_ROOT + os.sep):
		raise RunningInForgeRoot


def with_error_handler(function):
	def decorated_with_handler(*args, **kwargs):
		try:
			_assert_outside_of_forge_root()

			try:
				_assert_not_in_subdirectory_of_forge_root()
			except RunningInForgeRoot:
				print
				print """WARNING: running webmynd commands in a subdirectory of the forge build tools, this is probably a bad idea - please do your app development in a folder outside of the build tools"""
				print

			function(*args, **kwargs)
		except RunningInForgeRoot:
			# XXX: would use logging here, but there's no logging setup at this point - it gets setup
			# inside the command based on arguments
			# might be able to setup logging earlier on in this global handler?
			print
			print "ERROR: You're trying to run commands in the build tools directory, you need to move to another directory outside of this one first."
		except KeyboardInterrupt:
			sys.stdout.write('\n')
			LOG.info('exiting...')
			sys.exit(1)
		except ForgeError as e:
			# thrown by us, expected
			# XXX: want to print this out, going to sort out logging here.
			if LOG is None:
				print e
			else:
				LOG.error(e)
		except Exception as e:
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

def _assert_have_development_folder():
	if not os.path.exists('development'):
		raise ForgeError("No folder called 'development' found. You're trying to run your app but you haven't built it yet! Try wm-dev-build first.")

def _assert_have_production_folder():
	if not os.path.exists('production'):
		raise ForgeError("No folder called 'production' found. You're trying to run your app but you haven't built it yet! Try wm-prod-build first.")

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
	parser.add_argument('-d', '--device', help='Android device id (to run apk on a specific device)')
	parser.add_argument('platform', type=not_chrome, choices=['android', 'ios', 'firefox'])
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)

	if args.platform == 'android':
		_assert_have_development_folder()

		try:
			sdk = check_for_android_sdk(args.sdk)

			runAndroid(sdk, args.device)
		except CouldNotLocate as e:
			LOG.error(e)
	elif args.platform == 'ios':
		_assert_have_development_folder()

		config = build_config.load_app()
		runner = IOSRunner()
		runner.run_iphone_simulator_with(config['name'])
	elif args.platform == 'firefox':
		shutil.move(os.path.join('development', 'firefox', 'harness-options.json'),
			os.path.join('development', 'firefox', 'harness-options-bak.json'))
		try:
			with codecs.open(os.path.join('development', 'firefox', 'harness-options-bak.json'), encoding='utf8') as harness_file:
				harness_config = json.load(harness_file)
			run_app(os.path.join('development', 'firefox'), harness_config, "firefox", verbose=True)
		finally:
			shutil.move(os.path.join('development', 'firefox', 'harness-options-bak.json'),
				os.path.join('development', 'firefox', 'harness-options.json'))
			

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
		uuid = remote.create(name)
		remote.fetch_initial(uuid)
		LOG.info('App structure created. To proceed:')
		LOG.info('1) Put your code in the "%s" folder' % defaults.SRC_DIR)
		LOG.info('2) Run wm-dev-build to make a development build')
		LOG.info('3) Run wm-prod-build to make a production build')

def development_build():
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	
	parser = argparse.ArgumentParser(prog='wm-dev-build', description='Creates new local, unzipped development add-ons with your source and configuration')
	parser.add_argument('-f', '--full', action='store_true', help='Force a complete rebuild on the forge server')

	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	if not os.path.isdir(defaults.SRC_DIR):
		LOG.error('Source folder "%s" does not exist - have you run wm-create yet?' % defaults.SRC_DIR)
		raise ForgeError
	
	config = build_config.load()
	remote = Remote(config)
	remote.check_version()

	manager = Manager(config)

	templates_dir = manager.templates_for_config(defaults.APP_CONFIG_FILE)
	if templates_dir and not args.full:
		LOG.info('configuration is unchanged: using existing templates')
	else:
		if args.full:
			LOG.info('forcing rebuild of templates')
		else:
			LOG.info('configuration has changed: creating new templates')
		# configuration has changed: new template build!
		build_id = int(remote.build(development=True, template_only=True))
		# retrieve results of build
		templates_dir = manager.fetch_templates(build_id)
	
	# Windows often gives a permission error without a small wait
	tryAgain = 0
	while tryAgain < 5:
		time.sleep(tryAgain)
		try:
			tryAgain += 1
			shutil.rmtree('development', ignore_errors=True)
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

	if not os.path.isdir(defaults.SRC_DIR):
		LOG.error('Source folder "%s" does not exist - have you run wm-create yet?' % defaults.SRC_DIR)
		raise ForgeError

	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

	# build_id = int(remote.build(development=True, template_only=False))
	# TODO implement server-side packaging
	build_id = int(remote.build(development=False, template_only=False))
	
	LOG.info('fetching new WebMynd build')
	# remote.fetch_packaged(build_id, to_dir='production')
	# TODO implement server-side packaging
	remote.fetch_unpackaged(build_id, to_dir='production')
	LOG.info("Production build created. Use wm-run to run your app.")
