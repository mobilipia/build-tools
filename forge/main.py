"""Forge subcommands as well as the main entry point for the forge tools"""
import logging
import shutil
import sys

import argparse
import os

from os import path


import subprocess
import platform

import forge
from forge import defaults, build_config, ForgeError
from forge import build
from forge.generate import Generate
from forge.remote import Remote
from forge.templates import Manager
from forge.lib import try_a_few_times, AccidentHandler

LOG = logging.getLogger(__name__)
ENTRY_POINT_NAME = 'forge'
TARGETS_WE_CAN_PACKAGE_FOR = ('ios', 'android', 'web')

USING_DEPRECATED_COMMAND = None
USE_INSTEAD = None

_interactive_mode = True
ERROR_LOG_FILE = os.path.join(os.getcwd(), 'forge-error.log')

def _using_deprecated_command(command, use_instead):
	global USING_DEPRECATED_COMMAND, USE_INSTEAD
	USING_DEPRECATED_COMMAND = command
	USE_INSTEAD = use_instead

def _warn_about_deprecated_command():
	LOG.warning(
		"Using {command} which is now deprecated and will eventually be unsupported, instead, please use: '{new}'\n\n".format(
			command=USING_DEPRECATED_COMMAND,
			new=USE_INSTEAD,
		)
	)

class RunningInForgeRoot(Exception):
	pass

def _assert_outside_of_forge_root():
	if os.getcwd() == defaults.FORGE_ROOT:
		raise RunningInForgeRoot

def _assert_not_in_subdirectory_of_forge_root():
	cwd = str(os.getcwd())
	if cwd.startswith(defaults.FORGE_ROOT + os.sep):
		raise RunningInForgeRoot

def _check_working_directory_is_safe():
	_assert_outside_of_forge_root()
	try:
		_assert_not_in_subdirectory_of_forge_root()
	except RunningInForgeRoot:
		LOG.warning(
			"Working directory is a subdirectory of the forge build tools.\n"
			"This is probably a bad idea! Please do your app development in a folder outside\n"
			"of the build tools installation directory.\n"
		)

def with_error_handler(function):

	def decorated_with_handler(*args, **kwargs):
		global LOG
		try:
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
			sys.exit(1)
		except Exception as e:
			if LOG is None:
				LOG = logging.getLogger(__name__)
				LOG.addHandler(logging.StreamHandler())
				LOG.setLevel('DEBUG')
			LOG.debug("UNCAUGHT EXCEPTION: ", exc_info=True)
			LOG.error("Something went wrong that we didn't expect:")
			LOG.error(e)
			LOG.error("See %s for more details" % ERROR_LOG_FILE)
			LOG.error("Please contact support@trigger.io")
			sys.exit(1)

	return decorated_with_handler


def _setup_error_logging_to_file():
	"""Creates a handler which logs to a file in the case of an error, and
	attaches it to the root logger.
	"""
	file_handler = logging.FileHandler(ERROR_LOG_FILE, delay=True)
	file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)7s] %(message)s'))
	file_handler.setLevel('DEBUG')

	accident_handler = AccidentHandler(target=file_handler, capacity=9999, flush_level='ERROR')
	accident_handler.setLevel('DEBUG')

	logging.root.addHandler(accident_handler)


def _setup_logging_to_stdout(stdout_log_level):
	"""Creates a stream handler at the given log level and attaches it to
	the root logger.
	"""
	stream_handler = logging.StreamHandler()
	stream_handler.setLevel(stdout_log_level)
	stream_handler.setFormatter(logging.Formatter('[%(levelname)7s] %(message)s'))
	logging.root.addHandler(stream_handler)


def setup_logging(args):
	'Adjust logging parameters according to command line switches'
	global LOG
	if args.verbose and args.quiet:
		args.error('Cannot run in quiet and verbose mode at the same time')
	if args.verbose:
		stdout_log_level = logging.DEBUG
	elif args.quiet:
		stdout_log_level = logging.WARNING
	else:
		stdout_log_level = logging.INFO

	logging.root.setLevel('DEBUG')

	_setup_logging_to_stdout(stdout_log_level)
	_setup_error_logging_to_file()

	LOG = logging.getLogger(__name__)

	LOG.info('Forge tools running at version %s' % forge.get_version())

def add_general_options(parser):
	'Generic command-line arguments'
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	parser.add_argument('--no-interactive', action='store_true')
	parser.add_argument('--username', help='username used to login to the forge website')
	parser.add_argument('--password', help='password used to login to the forge website')

def handle_general_options(args):
	'Parameterise our option based on common command-line arguments'
	global _interactive_mode
	# TODO setup given user/password somewhere accessible by remote.py
	if args.username:
		forge.settings['username'] = args.username
	if args.password:
		forge.settings['password'] = args.password
	if args.no_interactive:
		_interactive_mode = False
	setup_logging(args)

def _assert_have_target_folder(directory, target):
	if not os.path.isdir(path.join(directory, target)):
		raise ForgeError("Can't run build for '%s', because you haven't built it!" % target)

def _assert_have_development_folder():
	if not os.path.exists('development'):
		message = (
			"No folder called 'development' found. You're trying to run your app but you haven't built it yet!\n"
			"Try {prog} build first."
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
	3) Use "Load unpacked extension" and browse to ./development/chrome
"""
			raise argparse.ArgumentTypeError(msg)
		return text

	parser.add_argument('-s', '--sdk', help='Path to the Android SDK')
	parser.add_argument('-d', '--device', help='Android device id (to run apk on a specific device)')
	parser.add_argument('-p', '--purge', action='store_true', help='If given will purge previous installs and any user data from the device before reinstalling.')
	parser.add_argument('platform', type=not_chrome, choices=['android', 'ios', 'firefox', 'web'])
	return parser.parse_args(args)

def run(unhandled_args):
	_check_working_directory_is_safe()
	args = _parse_run_args(unhandled_args)

	build_type_dir = 'development'
	_assert_have_development_folder()
	_assert_have_target_folder(build_type_dir, args.platform)

	generate_dynamic = build.import_generate_dynamic()

	# load local config file and mix in cmdline args
	extra_config = build_config.load_local()

	if 'sdk' not in extra_config:
		extra_config['sdk'] = None

	if args.sdk:
		extra_config['sdk'] = args.sdk

	generate_dynamic.customer_goals.run_app(
		generate_module=generate_dynamic,
		build_to_run=build.create_build(build_type_dir),
		target=args.platform,
		server=False,
		device=args.device,
		interactive=_interactive_mode,
		purge=args.purge,
		**extra_config
	)

def _parse_create_args(args):
	parser = argparse.ArgumentParser('%s create' % ENTRY_POINT_NAME, description='create a new application')
	parser.add_argument('-n', '--name')
	return parser.parse_args(args)

def create(unhandled_args):
	'Create a new development environment'
	_check_working_directory_is_safe()
	args = _parse_create_args(unhandled_args)
	config = build_config.load(expect_app_config=False)
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

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
		LOG.info('2) Run %s build to make a build' % ENTRY_POINT_NAME)
		LOG.info('3) Run %s run to test out your build' % ENTRY_POINT_NAME)

def _parse_development_build_args(args):
	parser = argparse.ArgumentParser('%s build' % ENTRY_POINT_NAME, description='Creates new local, unzipped development add-ons with your source and configuration')
	parser.add_argument('-f', '--full', action='store_true', help='Force a complete rebuild on the forge server')
	return parser.parse_args(args)

def development_build(unhandled_args):
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	_check_working_directory_is_safe()
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
	generator = Generate()
	generator.all('development', defaults.SRC_DIR)
	LOG.info("Development build created. Use {prog} run to run your app.".format(
		prog=ENTRY_POINT_NAME
	))

def _parse_package_args(args):
	parser = argparse.ArgumentParser(
		prog='%s package' % ENTRY_POINT_NAME,
		description='Package up a build for distribution',
	)
	parser.add_argument('platform', choices=TARGETS_WE_CAN_PACKAGE_FOR)
	parser.add_argument('-c', '--certificate', help="(iOS) name of the developer certificate to sign an iOS app with")
	parser.add_argument('-p', '--provisioning-profile', help="(iOS) path to a provisioning profile to use")

	parser.add_argument('--keystore', help="(Android) location of your release keystore")
	parser.add_argument('--storepass', help="(Android) password for your release keystore")
	parser.add_argument('--keyalias', help="(Android) alias of your release key")
	parser.add_argument('--keypass', help="(Android) password for your release key")
	parser.add_argument('--sdk', help="(Android) location of the Android SDK")

	return parser.parse_args(args)

def _package_dev_build_for_platform(platform, **kw):
	generate_dynamic = build.import_generate_dynamic()
	build_type_dir = 'development'

	generate_dynamic.customer_goals.package_app(
		generate_module=generate_dynamic,
		build_to_run=build.create_build(build_type_dir, targets=[platform]),
		target=platform,
		server=False,
		interactive = _interactive_mode,

		# pass in platform specific config via keyword args
		**kw
	)

@with_error_handler
def check(unhandled_args):
	'''
	Run basic linting on project JS to save the user some trouble.
	'''
	
	if not os.path.isdir(defaults.SRC_DIR):
		raise ForgeError(
			'Source folder "{src}" does not exist - have you run {prog} create yet?'.format(
				src=defaults.SRC_DIR,
				prog=ENTRY_POINT_NAME,
			)
		)
	
	LOG.info('Checking all JS files in src folder. No news is good news.')
	if sys.platform.startswith("linux"):
		if platform.architecture()[0] == '64bit':
			command = defaults.FORGE_ROOT + "/bin/jsl-64"
		else:
			command = defaults.FORGE_ROOT + "/bin/jsl"
	elif sys.platform.startswith("darwin"):
		command = defaults.FORGE_ROOT + "/bin/jsl-mac"
	elif sys.platform.startswith("win"):
		command = defaults.FORGE_ROOT + "/bin/jsl.exe"
	
	data = subprocess.Popen(
		[
			command,
			"-conf",
			defaults.FORGE_ROOT + "/jsl.conf",

			"-process",
			os.getcwd() + "/src/*.js",

			"-nologo",
			"-nofilelisting",
			"-nosummary"
		],
		stdout=subprocess.PIPE
	).communicate()[0]
	map(LOG.info, data.split('\n'))


def package(unhandled_args):
	#TODO: ensure dev build has been done first (probably lower down?)
	args = _parse_package_args(unhandled_args)
	extra_package_config = build_config.load_local()

	if args.platform == 'ios':
		if not sys.platform.startswith("darwin"):
			raise ForgeError("Detected that you're not running this from OSX. Currently, packaging iOS apps for devices is only possible on OSX.")

		if args.provisioning_profile is None:
			raise ForgeError("When packaging iOS apps, you need to provide a path to of a provisioning profile using -p or --provisioning-profile")

		abs_path_to_profile = os.path.abspath(args.provisioning_profile)

		extra_package_config.update(
			dict(
				provisioning_profile=abs_path_to_profile,
				certificate_to_sign_with=args.certificate,
			)
		)
	elif args.platform == 'android':
		abs_path_to_keystore = os.path.abspath(args.keystore) if args.keystore else args.keystore

		extra_package_config.update(
			dict(
				keystore=abs_path_to_keystore,
				storepass=args.storepass,
				keyalias=args.keyalias,
				keypass=args.keypass,
				sdk=args.sdk,
			)
		)
	elif args.platform == 'web':
		extra_package_config.update(
			# whatever extra parameters are required
			dict(
			)
		)

	_package_dev_build_for_platform(
		args.platform,
		**extra_package_config
	)

COMMANDS = {
	'create'  : create,
	'build'   : development_build,
	'run'     : run,
	'package' : package,
	'check'   : check
}

def _dispatch_command(command, other_args):
	subcommand = COMMANDS[command]
	with_error_handler(subcommand)(other_args)

def main():
	# The main entry point for the program.

	# Parses enough to figure out what subparser to hand off to, sets up logging and error handling
	# for the chosen sub-command.

	top_level_parser = argparse.ArgumentParser(prog='forge', add_help=False)
	top_level_parser.add_argument('command', choices=COMMANDS.keys())
	add_general_options(top_level_parser)

	handled_args, other_args = top_level_parser.parse_known_args()
	handle_general_options(handled_args)

	if USING_DEPRECATED_COMMAND:
		_warn_about_deprecated_command()

	_dispatch_command(handled_args.command, other_args)

if __name__ == "__main__":
	main()
