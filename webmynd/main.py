'Forge subcommands as well as the main entry point for the forge tools'
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
from webmynd.android import CouldNotLocate, run_android
from webmynd.ios import IOSRunner
from webmynd.lib import try_a_few_times
from webmynd import web

LOG = None
ENTRY_POINT_NAME = 'forge'

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
		global LOG
		try:
			_assert_outside_of_forge_root()

			try:
				_assert_not_in_subdirectory_of_forge_root()
			except RunningInForgeRoot:
				LOG.warning(
					"Working directory is a subdirectory of the forge build tools.\n"
					"This is probably a bad idea! Please do your app development in a folder outside\n"
					"of the build tools installation directory.\n"
				)

			function(*args, **kwargs)
		except RunningInForgeRoot:
			LOG.error(
				"You're trying to run commands in the build tools directory.\n"
				"You need to move to another directory outside of this one first.\n"
			)
		except KeyboardInterrupt:
			sys.stdout.write('\n')
			LOG.info('exiting...')
			sys.exit(1)
		except ForgeError as e:
			# thrown by us, expected
			LOG.error(e)
		except Exception as e:
			if LOG is None:
				LOG = logging.getLogger(__name__)
				LOG.addHandler(logging.StreamHandler())
				LOG.setLevel('DEBUG')
			LOG.debug("UNCAUGHT EXCEPTION: ", exc_info=True)
			LOG.error("Something went wrong that we didn't expect:");
			LOG.error(e);
			LOG.error("Please contact support@webmynd.com");
			sys.exit(1)

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
	LOG.info('Forge tools running at version %s' % webmynd.get_version())

def add_general_options(parser):
	'Generic command-line arguments'
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	parser.add_argument('--username', help='username used to login to the forge website')
	parser.add_argument('--password', help='password used to login to the forge website')
	
def handle_general_options(args):
	'Parameterise our option based on common command-line arguments'
	# TODO setup given user/password somewhere accessible by remote.py
	if args.username:
		webmynd.settings['username'] = args.username
	if args.password:
		webmynd.settings['password'] = args.password
	setup_logging(args)

def _assert_have_target_folder(directory, target):
	if not os.path.isdir(path.join(directory, target)):
		raise ForgeError("Can't run build for '%s', because you haven't built it!" % target) 

def _assert_have_development_folder():
	if not os.path.exists('development'):
		message = (
			"No folder called 'development' found. You're trying to run your app but you haven't built it yet!\n"
			"Try {prog} dev-build first."
		).format(
			prog=ENTRY_POINT_NAME
		)
		raise ForgeError(message)

def _assert_have_production_folder():
	if not os.path.exists('production'):
		message = (
			"No folder called 'production' found. You're trying to run your app but you haven't built it yet!\n"
			"Try {prog} prod-build first."
		).format(
			prog=ENTRY_POINT_NAME
		)
		raise ForgeError(message)

def _parse_run_args(args):
	parser = argparse.ArgumentParser(prog='%s run' % ENTRY_POINT_NAME, description='Run a built dev app on a particular platform')
	def not_chrome(text):
		if text == "chrome":
			msg = """

Currently it is not possible to launch a Chrome extension via this interface. The required steps are:

	1) Go to chrome:extensions in the Chrome browser
	2) Make sure "developer mode" is on (top right corner)')
	3) Use "Load unpacked extension" and browse to ./development/chrome"""
			raise argparse.ArgumentTypeError(msg)
		return text

	parser.add_argument('-s', '--sdk', help='Path to the Android SDK')
	parser.add_argument('-d', '--device', help='Android device id (to run apk on a specific device)')
	parser.add_argument('-p', '--production', help="Run a production build, rather than a development build", action='store_true')
	parser.add_argument('platform', type=not_chrome, choices=['android', 'ios', 'firefox'])
	return parser.parse_args(args)

def run(unhandled_args):
	args = _parse_run_args(unhandled_args)

	if args.production:
		build_type_dir = 'production'
		_assert_have_production_folder()
	else:
		build_type_dir = 'development'
		_assert_have_development_folder()
	_assert_have_target_folder(build_type_dir, args.platform)
	
	if args.platform == 'android':
		try:
			run_android(build_type_dir, args.sdk, args.device)
		except CouldNotLocate as e:
			LOG.error(e)
	elif args.platform == 'ios':
		config = build_config.load_app()
		runner = IOSRunner(build_type_dir)
		runner.run_iphone_simulator_with(config['name'])
	elif args.platform == 'firefox':
		original_harness_options = os.path.join(build_type_dir, 'firefox', 'harness-options.json')
		backup_harness_options = os.path.join(build_type_dir, 'firefox', 'harness-options-bak.json')
		shutil.move(original_harness_options, backup_harness_options)
		try:
			with codecs.open(backup_harness_options, encoding='utf8') as harness_file:
				harness_config = json.load(harness_file)
			from cuddlefish.runner import run_app
			run_app(os.path.join(build_type_dir, 'firefox'), harness_config, "firefox", verbose=True)
		finally:
			shutil.move(backup_harness_options, original_harness_options)

def _parse_create_args(args):
	parser = argparse.ArgumentParser('%s create' % ENTRY_POINT_NAME, description='create a new application')
	parser.add_argument('-n', '--name')
	return parser.parse_args(args)

def create(unhandled_args):
	'Create a new development environment'
	args = _parse_create_args(unhandled_args)
	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

	manager = Manager(config)

	if os.path.exists(defaults.SRC_DIR):
		raise ForgeError('Source folder "%s" already exists, if you really want to create a new app you will need to remove it!' % defaults.SRC_DIR)
	else:
		if args.name:
			name = args.name
		else:
			name = raw_input('Enter app name: ')
		uuid = remote.create(name)
		remote.fetch_initial(uuid)
		LOG.info('App structure created. To proceed:')
		LOG.info('1) Put your code in the "%s" folder' % defaults.SRC_DIR)
		LOG.info('2) Run %s dev-build to make a development build' % ENTRY_POINT_NAME)
		LOG.info('3) Run %s prod-build to make a production build' % ENTRY_POINT_NAME)

def _parse_development_build_args(args):
	parser = argparse.ArgumentParser('%s dev-build' % ENTRY_POINT_NAME, description='Creates new local, unzipped development add-ons with your source and configuration')
	parser.add_argument('-f', '--full', action='store_true', help='Force a complete rebuild on the forge server')
	return parser.parse_args(args)

def development_build(unhandled_args):
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	args = _parse_development_build_args(unhandled_args)

	if not os.path.isdir(defaults.SRC_DIR):
		raise ForgeError(
			'Source folder "{src}" does not exist - have you run {prog} create yet?'.format(
				src=defaults.SRC_DIR,
				prog=ENTRY_POINT_NAME,
			)
		)

	config = build_config.load()
	remote = Remote(config)
	manager = Manager(config)

	instructions_dir = defaults.INSTRUCTIONS_DIR
	templates_dir = manager.templates_for_config(defaults.APP_CONFIG_FILE)
	if templates_dir and not args.full:
		LOG.info('configuration is unchanged: using existing templates')
	else:
		if args.full:
			LOG.info('forcing rebuild of templates')
		else:
			LOG.info('configuration has changed: creating new templates')

		remote.check_version()

		# configuration has changed: new template build!
		build_id = int(remote.build(development=True, template_only=True))
		# retrieve results of build
		templates_dir = manager.fetch_templates(build_id, clean=args.full)

		# have templates - now fetch injection instructions
		remote.fetch_generate_instructions(build_id, instructions_dir)

	def move_files_across():
		shutil.rmtree('development', ignore_errors=True)
		shutil.copytree(templates_dir, 'development')
		shutil.rmtree(path.join('development', 'generate_dynamic'), ignore_errors=True)

	# Windows often gives a permission error without a small wait
	try_a_few_times(move_files_across)

	# have templates and instructions - inject code
	generator = Generate(defaults.APP_CONFIG_FILE)
	generator.all('development', defaults.SRC_DIR)
	LOG.info("Development build created. Use {prog} to run your app.".format(
		prog=ENTRY_POINT_NAME
	))

def _parse_production_build_args(args):
	parser = argparse.ArgumentParser(
		prog='%s prod-build' % ENTRY_POINT_NAME,
		description='Start a new production build and retrieve the packaged and unpackaged output'
	)

	add_general_options(parser)
	return parser.parse_args(args)

def production_build(unhandled_args):
	'Trigger a new build'
	# TODO commonality between this and development_build
	_parse_production_build_args(unhandled_args)

	if not os.path.isdir(defaults.SRC_DIR):
		raise ForgeError('Source folder "%s" does not exist - have you run %s create yet?' % defaults.SRC_DIR)

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

	LOG.info('fetching new Forge build')
	# remote.fetch_packaged(build_id, to_dir='production')
	# TODO implement server-side packaging
	remote.fetch_unpackaged(build_id, to_dir='production')
	LOG.info("Production build created. Use %s run to run your app." % ENTRY_POINT_NAME)

def run_web_server(other_args):
	web.run_server()

COMMANDS = {
	'create': create,
	'dev-build': development_build,
	'prod-build': production_build,
	'run': run,
	'web': run_web_server,
}

if __name__ == "__main__":
	'''The main entry point for the program.

	 Parses enough to figure out what subparser to hand off to, sets up logging and error handling
	 for the chosen sub-command.
	 '''

	top_level_parser = argparse.ArgumentParser(prog='forge', add_help=False)
	top_level_parser.add_argument('command', choices=COMMANDS.keys())
	add_general_options(top_level_parser)

	handled_args, other_args = top_level_parser.parse_known_args()
	handle_general_options(handled_args)

	subcommand = COMMANDS[handled_args.command]
	with_error_handler(subcommand)(other_args)
