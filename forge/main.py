"""Forge subcommands as well as the main entry point for the forge tools"""
import argparse
import logging
import os
from os import path
import platform
import shutil
import subprocess
import sys

import forge
from forge import defaults, build_config, ForgeError
from forge import build
from forge.generate import Generate
from forge.remote import Remote
from forge.templates import Manager
from forge.lib import try_a_few_times, AccidentHandler

LOG = logging.getLogger(__name__)
ENTRY_POINT_NAME = 'forge'
TARGETS_WE_CAN_RUN_FOR = ('firefox', 'ios', 'android', 'web')
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
class ArgumentError(Exception):
	pass

def _assert_outside_of_forge_root():
	if os.getcwd() == defaults.FORGE_ROOT:
		raise RunningInForgeRoot

def _assert_not_in_subdirectory_of_forge_root():
	cwd = str(os.getcwd())
	if cwd.startswith(defaults.FORGE_ROOT + os.sep):
		raise RunningInForgeRoot

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
				LOG.setLevel(logging.DEBUG)
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
	file_handler.setLevel(logging.DEBUG)

	accident_handler = AccidentHandler(target=file_handler, capacity=9999, flush_level='ERROR')
	accident_handler.setLevel(logging.DEBUG)

	logging.root.addHandler(accident_handler)


def _setup_logging_to_stdout(stdout_log_level):
	"""Creates a stream handler at the given log level and attaches it to
	the root logger.
	"""
	stream_handler = logging.StreamHandler()
	stream_handler.setLevel(stdout_log_level)
	stream_handler.setFormatter(logging.Formatter('[%(levelname)7s] %(message)s'))
	logging.root.addHandler(stream_handler)


def setup_logging(settings):
	'Adjust logging parameters according to command line switches'
	global LOG
	verbose = settings.get('verbose')
	quiet = settings.get('quiet')
	if verbose and quiet:
		raise ArgumentError('Cannot run in quiet and verbose mode at the same time')
	if verbose:
		stdout_log_level = logging.DEBUG
	elif quiet:
		stdout_log_level = logging.WARNING
	else:
		stdout_log_level = logging.INFO

	logging.root.setLevel(logging.DEBUG)

	_setup_logging_to_stdout(stdout_log_level)
	_setup_error_logging_to_file()

	LOG = logging.getLogger(__name__)

	LOG.info('Forge tools running at version %s' % forge.get_version())

def add_primary_options(parser):
	'''Top-level command-line arguments for settings which affect the running of
	any command for any platform
	'''
	parser.add_argument('command', choices=COMMANDS.keys())
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	parser.add_argument('--username', help='your email address used to login to the forge website')
	parser.add_argument('--password', help='password used to login to the forge website')
	parser.add_argument('--name', help='name of the new app (used during "create" only)')

def handle_primary_options(args):
	'Parameterise our option based on common command-line arguments'
	parser = argparse.ArgumentParser(prog='forge', add_help=False)
	add_primary_options(parser)

	handled_args, other_args = parser.parse_known_args()

	# TODO setup given user/password somewhere accessible by remote.py
	forge.settings['command'] = handled_args.command
	if handled_args.username:
		forge.settings['username'] = handled_args.username
	if handled_args.password:
		forge.settings['password'] = handled_args.password
	forge.settings['verbose'] = bool(handled_args.verbose)
	forge.settings['quiet'] = bool(handled_args.quiet)
	if handled_args.name:
		forge.settings['name'] = handled_args.name

	try:
		setup_logging(forge.settings)
	except ArgumentError as e:
		parser.error(e)

	return other_args

def _add_create_options(parser):
	parser.description = 'create a new application'
	parser.add_argument('--name', help='name of the application to create')
def _handle_create_options(handled):
	if handled.name:
		forge.settings['name'] = handled.name

def _add_build_options(parser):
	parser.description = 'Creates new local, unzipped development add-ons with your source and configuration'
	parser.add_argument('-f', '--full', action='store_true', help='force a complete rebuild of your app')
def _handle_build_options(handled):
	forge.settings['full'] = bool(handled.full)

def _add_run_options(parser):
	parser.description = 'Run a built app on a particular platform'
	def not_chrome(text):
		if text == "chrome":
			msg = """

Currently it is not possible to launch a Chrome extension via this interface. The required steps are:

	1) Go to chrome:extensions in the Chrome browser
	2) Make sure "developer mode" is on (top right corner)')
	3) Use "Load unpacked extension" and browse to {cwd}/development/chrome
""".format(cwd=path.abspath(os.getcwd()))
			return parser.error(msg)
		return text
	parser.add_argument('platform', type=not_chrome, choices=TARGETS_WE_CAN_RUN_FOR)
def _handle_run_options(handled):
	forge.settings['platform'] = handled.platform

def _add_package_options(parser):
	parser.description='Package up a build for distribution'
	parser.add_argument('platform', choices=TARGETS_WE_CAN_PACKAGE_FOR)
def _handle_package_options(handled):
	forge.settings['platform'] = handled.platform
	
def handle_secondary_options(command, args):
	parser = argparse.ArgumentParser(
		prog="{entry} {command}".format(entry=ENTRY_POINT_NAME, command=command)
	)
	options_handlers = {
		"create": (_add_create_options, _handle_create_options),
		"build": (_add_build_options, _handle_build_options),
		"run": (_add_run_options, _handle_run_options),
		"package": (_add_package_options, _handle_package_options),
	}

	# add command-specific arguments
	options_handlers[command][0](parser)

	handled, other = parser.parse_known_args(args)

	# parse command-specific arguments
	options_handlers[command][1](handled)

	return other

def create(unhandled_args):
	'Create a new development environment'
	_check_working_directory_is_safe()
	config = build_config.load()
	remote = Remote(config)
	try:
		remote.check_version()
	except Exception as e:
		LOG.error(e)
		return 1

	if os.path.exists(defaults.SRC_DIR):
		raise ForgeError('Source folder "%s" already exists, if you really want to create a new app you will need to remove it!' % defaults.SRC_DIR)
	else:
		if "name" in forge.settings and forge.settings["name"]:
			name = forge.settings["name"]
		else:
			name = raw_input('Enter app name: ')
		uuid = remote.create(name)
		remote.fetch_initial(uuid)
		LOG.info('App structure created. To proceed:')
		LOG.info('1) Put your code in the "%s" folder' % defaults.SRC_DIR)
		LOG.info('2) Run %s build to make a build' % ENTRY_POINT_NAME)
		LOG.info('3) Run %s run to test out your build' % ENTRY_POINT_NAME)

def development_build(unhandled_args):
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	_check_working_directory_is_safe()

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
	if templates_dir and not forge.settings['full']:
		LOG.info('configuration is unchanged: using existing templates')
	else:
		if forge.settings['full']:
			LOG.info('forcing rebuild of templates')
		else:
			LOG.info('configuration has changed: creating new templates')

		remote.check_version()

		# configuration has changed: new template build!
		build_id = int(remote.build(development=True, template_only=True))
		# retrieve results of build
		templates_dir = manager.fetch_templates(build_id, clean=forge.settings['full'])

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
	generator.all('development', defaults.SRC_DIR, extra_args=unhandled_args)
	LOG.info("Development build created. Use {prog} run to run your app.".format(
		prog=ENTRY_POINT_NAME
	))

def run(unhandled_args):
	_check_working_directory_is_safe()
	build_type_dir = 'development'
	_assert_have_development_folder()
	_assert_have_target_folder(build_type_dir, forge.settings['platform'])

	generate_dynamic = build.import_generate_dynamic()

	build_to_run = build.create_build(
		build_type_dir,
		targets=[forge.settings['platform']],
		extra_args=unhandled_args,
	)

	generate_dynamic.customer_goals.run_app(
		generate_module=generate_dynamic,
		build_to_run=build_to_run,
		server=False,
	)

def package(unhandled_args):
	#TODO: ensure dev build has been done first (probably lower down?)
	generate_dynamic = build.import_generate_dynamic()
	build_type_dir = 'development'
	build_to_run = build.create_build(
		build_type_dir,
		targets=[forge.settings['platform']],
		extra_args=unhandled_args,
	)

	generate_dynamic.customer_goals.package_app(
		generate_module=generate_dynamic,
		build_to_run=build_to_run,
		server=False,
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

def _dispatch_command(command, other_args):
	other_other_args = handle_secondary_options(command, other_args)

	subcommand = COMMANDS[command]
	with_error_handler(subcommand)(other_other_args)

def main():
	# The main entry point for the program.

	# Parses enough to figure out what subparser to hand off to, sets up logging and error handling
	# for the chosen sub-command.

	other_args = handle_primary_options(sys.argv)

	if USING_DEPRECATED_COMMAND:
		_warn_about_deprecated_command()

	_dispatch_command(forge.settings['command'], other_args)

COMMANDS = {
	'create'  : create,
	'build'   : development_build,
	'run'     : run,
	'package' : package,
	'check'   : check
}

if __name__ == "__main__":
	main()
