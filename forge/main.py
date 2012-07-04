"""Forge subcommandsas well as the main entry point for the forge tools"""
import argparse
import logging
import os
from os import path
import shutil
import sys
import traceback
from StringIO import StringIO
import json
import threading
import Queue

import forge
from forge import defaults, build_config, ForgeError
from forge import build as forge_build
from forge.generate import Generate
from forge.remote import Remote, UpdateRequired
from forge.templates import Manager
from forge.lib import try_a_few_times, AccidentHandler, FilterHandler, CurrentThreadHandler

from forge import async
from forge import cli


LOG = logging.getLogger(__name__)
ENTRY_POINT_NAME = 'forge'
TARGETS_WE_CAN_RUN_FOR = ('firefox', 'ios', 'android', 'web', 'wp', 'chrome')
TARGETS_WE_CAN_PACKAGE_FOR = ('ios', 'android', 'web', 'wp', 'chrome')

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

def _assert_outside_of_forge_root(app_path):
	if app_path == defaults.FORGE_ROOT:
		raise RunningInForgeRoot

def _assert_not_in_subdirectory_of_forge_root(app_path):
	cwd = str(app_path)
	if cwd.startswith(defaults.FORGE_ROOT + os.sep):
		raise RunningInForgeRoot

def _assert_have_target_folder(directory, target):
	if not os.path.isdir(path.join(directory, target)):
		raise ForgeError(
			"Can't run build for '{target}', because you haven't built it!\n"
			"If you're interested in targetting {target}, please contact support@trigger.io to sign up for one of our paid plans.".format(target=target)
		)

def _assert_have_development_folder():
	if not os.path.exists('development'):
		message = (
			"No folder called 'development' found. You're trying to run your app but you haven't built it yet!\n"
			"Try {prog} build first."
		).format(
			prog=ENTRY_POINT_NAME
		)
		raise ForgeError(message)

def _check_working_directory_is_safe(app_path=None):
	if app_path is None:
		app_path = os.getcwd()

	_assert_outside_of_forge_root(app_path)
	try:
		_assert_not_in_subdirectory_of_forge_root(app_path)
	except RunningInForgeRoot:
		LOG.warning(
			"Working directory is a subdirectory of the forge build tools.\n"
			"This is probably a bad idea! Please do your app development in a folder outside\n"
			"of the build tools installation directory.\n"
		)

def _setup_error_logging_to_file():
	"""Creates a handler which logs to a file in the case of an error, and
	attaches it to the root logger.
	"""
	file_handler = logging.FileHandler(ERROR_LOG_FILE, delay=True)
	file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)7s] %(message)s'))
	file_handler.setLevel(logging.DEBUG)

	accident_handler = AccidentHandler(target=file_handler, capacity=9999, flush_level='ERROR')
	accident_handler.setLevel(logging.DEBUG)

	thread_handler = CurrentThreadHandler(target_handler=accident_handler)
	thread_handler.setLevel(logging.DEBUG)

	logging.root.addHandler(thread_handler)


def _setup_logging_to_stdout(stdout_log_level):
	"""Creates a stream handler at the given log level and attaches it to
	the root logger.
	"""
	stream_handler = logging.StreamHandler()
	stream_handler.setLevel(stdout_log_level)
	stream_handler.setFormatter(logging.Formatter('[%(levelname)7s] %(message)s'))
	
	handler = CurrentThreadHandler(target_handler=stream_handler)
	handler.setLevel(stdout_log_level)
	logging.root.addHandler(handler)

def _filter_requests_logging():
	"""Stops requests from logging to info!"""
	logging.getLogger('requests').setLevel(logging.ERROR)

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
	_filter_requests_logging()

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

	handled_args, other_args = parser.parse_known_args(args)

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
	parser.add_argument('platform', choices=TARGETS_WE_CAN_RUN_FOR)

def _handle_run_options(handled):
	forge.settings['platform'] = handled.platform


def _add_package_options(parser):
	parser.description='Package up a build for distribution'
	parser.add_argument('platform', choices=TARGETS_WE_CAN_PACKAGE_FOR)

def _handle_package_options(handled):
	forge.settings['platform'] = handled.platform


def _add_check_options(parser):
	parser.description='Do some testing on the current local configuration settings'

def _handle_check_options(handled):
	pass


def _add_migrate_options(parser):
	parser.description='Update app to the next major platform version'
def _handle_migrate_options(handled):
	pass


def _add_reload_options(parser):
	parser.description='Run reload commands'
def _handle_reload_options(handled):
	pass

def handle_secondary_options(command, args):
	parser = argparse.ArgumentParser(
		prog="{entry} {command}".format(entry=ENTRY_POINT_NAME, command=command),
		epilog="For more detailed information, see http://current-docs.trigger.io/tools/commands.html",
	)
	options_handlers = {
		"create": (_add_create_options, _handle_create_options),
		"build": (_add_build_options, _handle_build_options),
		"run": (_add_run_options, _handle_run_options),
		"package": (_add_package_options, _handle_package_options),
		"check": (_add_check_options, _handle_check_options),
		"migrate": (_add_migrate_options, _handle_migrate_options),
		"reload": (_add_reload_options, _handle_reload_options),
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
	remote.check_version()

	if os.path.exists(defaults.SRC_DIR):
		raise ForgeError('Source folder "%s" already exists, if you really want to create a new app you will need to remove it!' % defaults.SRC_DIR)
	else:
		if "name" in forge.settings and forge.settings["name"]:
			name = forge.settings["name"]
		else:
			event_id = async.current_call().emit('question', schema={
				'description': 'Enter details for app',
				'properties': {
					'name': {
						'type': 'string',
						'title': 'App Name',
						'description': 'This name is what your application will be called on devices. You can change it later through config.json.'
					}
				}
			})

			name = async.current_call().wait_for_response(event_id)['data']['name']
		uuid = remote.create(name)
		remote.fetch_initial(uuid)
		LOG.info("Building app for the first time...")
		development_build([])
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
	remote.check_version()
	manager = Manager(config)

	instructions_dir = defaults.INSTRUCTIONS_DIR
	if forge.settings.get('full', False):
		# do this first, so that bugs in generate_dynamic can always be nuked with a -f
		LOG.debug("Full rebuild requested: removing previous templates")
		shutil.rmtree(instructions_dir, ignore_errors=True)

	app_config = build_config.load_app()
	reload_result = remote._api_post('reload/buildevents/%s' % app_config['uuid'], files={'config': StringIO(json.dumps(app_config))})
	
	reload_config = json.loads(reload_result['config'])
	reload_config_hash = reload_result['config_hash']
	
	config_changed = manager.need_new_templates_for_config()
	should_rebuild = remote.server_says_should_rebuild()
	server_changed = should_rebuild['should_rebuild']
	reason = should_rebuild['reason']
	stable_platform = should_rebuild['stable_platform']
	platform_state = should_rebuild['platform_state']
	if config_changed or server_changed:
		if config_changed:
			LOG.info("Your app configuration has changed: we need to rebuild your app")
		elif server_changed:
			LOG.debug("Server requires rebuild: {reason}".format(reason=reason))
			LOG.info("Your Forge platform has been updated: we need to rebuild your app")

		# configuration has changed: new template build!
		build = remote.build(development=True, template_only=True, config=reload_config)
		manager.fetch_template_apps_and_instructions(build)
	else:
		LOG.info('Configuration is unchanged: using existing templates')
	
	app_config = build_config.load_app()
	cur_version = app_config['platform_version'].split('.')
	stable_version = stable_platform.split('.')
	
	# Non-standard platform
	if cur_version[0][:1] != 'v':
		LOG.warning("Platform version: "+app_config['platform_version']+" is a non-standard platform version, it may not be receiving updates and it is recommended you update to the stable platform version: "+stable_platform)
	# Minor version
	elif len(cur_version) > 2:
		LOG.warning("Platform version: "+app_config['platform_version']+" is a minor platform version, it may not be receiving updates, it is recommended you update to a major platform version")
	# Old version
	elif int(cur_version[0][1:]) < int(stable_version[0][1:]) or (int(cur_version[0][1:]) == int(stable_version[0][1:]) and int(cur_version[1]) < int(stable_version[1])):
		LOG.warning("Platform version: "+app_config['platform_version']+" is no longer the current platform version, it is recommended you migrate to a newer version using the 'forge migrate' command. See http://current-docs.trigger.io/release-notes.html for more details")
	
	# Deprecated version
	if platform_state == "deprecated":
		LOG.warning("Platform version: "+app_config['platform_version']+" is deprecated, it is highly recommended you migrate to a newer version as soon as possible.")

	def move_files_across():
		shutil.rmtree('development', ignore_errors=True)
		shutil.copytree(defaults.TEMPLATE_DIR, 'development')
		shutil.rmtree(path.join('development', 'generate_dynamic'), ignore_errors=True)

	# Windows often gives a permission error without a small wait
	try_a_few_times(move_files_across)

	# have templates and instructions - inject code
	generator = Generate()
	# Put config hash in config object for local generation
	# copy first as mutating dict makes assertions about previous uses tricky
	reload_config_for_local = reload_config.copy()
	reload_config_for_local['config_hash'] = reload_config_hash
	generator.all('development', defaults.SRC_DIR, extra_args=unhandled_args, config=reload_config_for_local)
	LOG.info("Development build created. Use {prog} run to run your app.".format(
		prog=ENTRY_POINT_NAME
	))

def run(unhandled_args):
	_check_working_directory_is_safe()
	build_type_dir = 'development'
	_assert_have_development_folder()
	_assert_have_target_folder(build_type_dir, forge.settings['platform'])

	generate_dynamic = forge_build.import_generate_dynamic()

	build_to_run = forge_build.create_build(
		build_type_dir,
		targets=[forge.settings['platform']],
		extra_args=unhandled_args,
	)

	generate_dynamic.customer_goals.run_app(
		generate_module=generate_dynamic,
		build_to_run=build_to_run,
	)

def package(unhandled_args):
	#TODO: ensure dev build has been done first (probably lower down?)
	generate_dynamic = forge_build.import_generate_dynamic()
	build_type_dir = 'development'
	build_to_run = forge_build.create_build(
		build_type_dir,
		targets=[forge.settings['platform']],
		extra_args=unhandled_args,
	)

	generate_dynamic.customer_goals.package_app(
		generate_module=generate_dynamic,
		build_to_run=build_to_run,
	)

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
	
	try:
		generate_dynamic = forge_build.import_generate_dynamic()
	except ForgeError:
		# don't have generate_dynamic available yet
		LOG.info("Unable to check local settings until a build has completed")
		return
	build_to_run = forge_build.create_build(
		"development",
		targets=[],
		extra_args=unhandled_args,
	)
	generate_dynamic.customer_goals.check_settings(
		generate_dynamic,
		build_to_run,
	)

def migrate(unhandled_args):
	'''
	Migrate the app to the next major platform (if possible)
	'''
	if not os.path.isdir(defaults.SRC_DIR):
		raise ForgeError(
			'Source folder "{src}" does not exist - have you run {prog} create yet?'.format(
				src=defaults.SRC_DIR,
				prog=ENTRY_POINT_NAME,
			)
		)
	
	try:
		generate_dynamic = forge_build.import_generate_dynamic()
	except ForgeError:
		# don't have generate_dynamic available yet
		raise ForgeError("Unable to migrate until a build has completed")
	build_to_run = forge_build.create_build(
		"development",
		targets=[],
		extra_args=unhandled_args,
	)
	generate_dynamic.customer_goals.migrate_app(
		generate_dynamic,
		build_to_run,
	)

def reload(unhandled_args):
	'''
	Run reload module command
	'''
	if not os.path.isdir(defaults.SRC_DIR):
		raise ForgeError(
			'Source folder "{src}" does not exist - have you run {prog} create yet?'.format(
				src=defaults.SRC_DIR,
				prog=ENTRY_POINT_NAME,
			)
		)
	
	try:
		generate_dynamic = forge_build.import_generate_dynamic()
	except ForgeError:
		# don't have generate_dynamic available yet
		raise ForgeError("Unable to use reload until a build has completed")

	build_to_run = forge_build.create_build(
		"development",
		targets=[],
	)
	generate_dynamic.reload.run_command(
		build_to_run,
		unhandled_args,
	)

def _dispatch_command(command, other_args):
	"""Runs our subcommand in a separate thread, and handles events emitted by it"""
	call = None
	task_thread = None
	try:
		other_other_args = handle_secondary_options(command, other_args)

		subcommand = COMMANDS[command]

		# setup enough stuff so the target function can communicate back using events
		call = async.Call(
			call_id=0,
			target=subcommand,
			args=(other_other_args, ),
			input=Queue.Queue(),
			output=Queue.Queue(),
		)
		async.set_current_call(call, thread_local=True)

		# capture logging on any thread but this one and turn it into events
		handler = async.CallHandler(call)
		handler.setLevel(logging.DEBUG)

		current_thread = threading.current_thread().name
		filtered_handler = FilterHandler(handler, lambda r: r.threadName != current_thread)
		filtered_handler.setLevel(logging.DEBUG)

		logging.root.addHandler(filtered_handler)
		logging.root.setLevel(logging.DEBUG)

		task_thread = threading.Thread(target=call.run)
		task_thread.daemon = True
		task_thread.start()

		while True:
			try:
				# KeyboardInterrupts aren't seen until the .get() completes :S
				# So we set a timeout here to make sure we receive it
				next_event = call._output.get(block=True, timeout=1)
			except Queue.Empty:
				continue
			event_type = next_event['type']

			if event_type == 'question':
				answer = cli.ask_question(next_event)

				call.input({
					'eventId': next_event['eventId'],
					'data': answer,
				})

			if event_type == 'progressStart':
				cli.start_progress(next_event)

			if event_type == 'progressEnd':
				cli.end_progress(next_event)

			if event_type == 'progress':
				cli.progress_bar(next_event)

			# TODO: handle situation of logging while progress bar is running
			# e.g. extra newline before using LOG.log
			if event_type == 'log':
				# all logging in our task thread comes out as events, which we then
				# plug back into the logging system, which then directs it to file/console output
				logging_level = getattr(logging, next_event.get('level', 'DEBUG'))
				LOG.log(logging_level, next_event.get('message', ''))

			elif event_type == 'success':
				return 0

			elif event_type == 'error':
				# re-raise exception originally from other thread/process
				try:
					raise call.exception

				except RunningInForgeRoot:
					LOG.error(
						"You're trying to run commands in the build tools directory.\n"
						"You need to move to another directory outside of this one first.\n"
					)

				except UpdateRequired:
					LOG.info("An update to these command line tools is required, downloading...")

					# TODO: refactor so that we don't need to instantiate Remote here
					config = build_config.load()
					remote = Remote(config)
					try:
						remote.update()
						LOG.info("Update complete, run your command again to continue")

					except Exception as e:
						LOG.error("Upgrade process failed: %s" % e)
						LOG.debug("%s" % traceback.format_exc(e))
						LOG.error("You can get the tools from https://trigger.io/api/latest_tools and extract them yourself")
						LOG.error("Contact support@trigger.io if you have any further issues")

				except ForgeError as e:
					# thrown by us, expected
					LOG.error(next_event.get('message'))
					LOG.debug(str(next_event.get('traceback')))

				except Exception:
					LOG.error("Something went wrong that we didn't expect:")
					LOG.error(next_event.get('message'))
					LOG.debug(str(next_event.get('traceback')))

					LOG.error("See %s for more details" % ERROR_LOG_FILE)
					LOG.error("Please contact support@trigger.io")

				return 1
	except KeyboardInterrupt:
		sys.stdout.write('\n')
		LOG.info('Exiting...')
		if call:
			call.interrupt()
			task_thread.join(timeout=5)
		return 1

def main():
	# The main entry point for the program.

	# Parses enough to figure out what subparser to hand off to, sets up logging and error handling
	# for the chosen sub-command.

	other_args = handle_primary_options(sys.argv[1:])

	if USING_DEPRECATED_COMMAND:
		_warn_about_deprecated_command()

	return _dispatch_command(forge.settings['command'], other_args)

COMMANDS = {
	'create'  : create,
	'build'   : development_build,
	'run'     : run,
	'package' : package,
	'check'   : check,
	'migrate' : migrate,
	'reload' : reload
}

if __name__ == "__main__":
	main()
