import logging
import warnings
import os as real_os
import mock
from nose.tools import ok_, eq_, raises

import forge
from forge.tests import dummy_config, lib
from forge import main, defaults
from os import path

@mock.patch('forge.main._setup_logging_to_stdout')
@mock.patch('forge.main._setup_error_logging_to_file')
@mock.patch('forge.main.logging')
def _logging_test(args, level, logging, _setup_error_logging_to_file, _setup_logging_to_stdout):
	main.setup_logging(args)

	_setup_error_logging_to_file.assert_called_once_with()
	_setup_logging_to_stdout.assert_called_once_with(getattr(logging, level))
	logging.getLogger.assert_called_once_with('forge.main')


def test_verbose():
	args = mock.Mock()
	args.verbose = True
	args.quiet = False
	_logging_test(args, 'DEBUG')
def test_quiet():
	args = mock.Mock()
	args.verbose = False
	args.quiet = True
	_logging_test(args, 'WARNING')
def test_default():
	args = mock.Mock()
	args.verbose = False
	args.quiet = False
	_logging_test(args, 'INFO')
def test_both():
	args = mock.Mock()
	args.quiet = True
	args.verbose = True
	_logging_test(args, 'DEBUG')
	ok_(args.error.called)

general_argparse = [
	(('-v', '--verbose'), {'action': 'store_true'}),
	(('-q', '--quiet'), {'action': 'store_true'}),
	(('--username', ), {'help': 'username used to login to the forge website'}),
	(('--password', ), {'help': 'password used to login to the forge website'}),
]

class TestCreate(object):
	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os')
	@mock.patch('forge.main.Remote')
	@mock.patch('forge.main.argparse')
	def test_normal(self, argparse, Remote, mock_os, build_config):
		mock_os.sep = real_os.sep
		parser = argparse.ArgumentParser.return_value
		parser.parse_args.return_value.name = None

		mock_os.path.exists.return_value = False
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'
		remote = Remote.return_value
		build_config.load.return_value = dummy_config()

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			main.create([])

		mock_os.path.exists.assert_called_once_with(defaults.SRC_DIR)
		remote.create.assert_called_once_with(mock_raw_input.return_value)
		remote.fetch_initial.assert_called_once_with(remote.create.return_value)

	@mock.patch('forge.main.os')
	@mock.patch('forge.main.Remote')
	@mock.patch('forge.main.argparse')
	@raises(forge.ForgeError)
	def test_user_dir_there(self, argparse, Remote, mock_os):
		mock_os.sep = real_os.sep
		parser = argparse.ArgumentParser.return_value
		mock_os.path.exists.return_value = True
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'
		remote = Remote.return_value

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			main.create([])

class TestRun(object):
	@mock.patch('forge.main.build')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_have_development_folder')
	@mock.patch('forge.main._assert_have_target_folder')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	def test_not_android(self, _assert_have_target_folder, _assert_have_development_folder,
			argparse, build):
		parser = argparse.ArgumentParser.return_value
		args = mock.Mock()
		args.platform = 'chrome'
		parser.parse_args.return_value = args

		main.run([])

		parser.parse_args.assert_called_once()

	@mock.patch('forge.main.build')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_have_target_folder')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	def test_found_jdk_and_sdk(self, _assert_have_development_folder, argparse, build):
		main._assert_have_development_folder = mock.Mock()
		parser = argparse.ArgumentParser.return_value
		args = mock.Mock()
		args.platform = 'android'
		args.device = 'device'
		args.sdk = 'sdk'
		parser.parse_args.return_value = args

		values = ['jdk', 'sdk']
		def get_dir(*args, **kw):
			return values.pop()

		main.run([])

		parser.parse_args.assert_called_once()
		build.create_build.assert_called_once()
		build.create_build.return_value.run.assert_called_once()

class Test_AssertNotSubdirectoryOfForgeRoot(object):
	@mock.patch('forge.main.os.getcwd')
	@raises(main.RunningInForgeRoot)
	def test_raises_in_subdirectory(self, getcwd):
		getcwd.return_value = path.join(defaults.FORGE_ROOT, 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

	@mock.patch('forge.main.os.getcwd')
	def test_not_confused_by_similar_directory(self, getcwd):
		getcwd.return_value = path.join(defaults.FORGE_ROOT + '-app', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

	@mock.patch('forge.main.os.getcwd')
	def test_ok_when_not_in_subdirectory(self, getcwd):
		getcwd.return_value = path.join('not','forge','tools', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

class Test_AssertOutsideOfForgeRoot(object):

	@mock.patch('forge.main.os')
	@raises(main.RunningInForgeRoot)
	def test_raises_exception_inside_forge_root(self, os):
		os.getcwd = mock.Mock()
		os.getcwd.return_value = defaults.FORGE_ROOT
		main._assert_outside_of_forge_root()

	@mock.patch('forge.main.os')
	def test_nothing_happens_outside_of_forge_root(self, os):
		os.getcwd = mock.Mock()
		os.getcwd.return_value = path.join('some', 'other', 'dir')
		main._assert_outside_of_forge_root()

class TestBuild(object):
	def _check_common_setup(self, parser, Remote):
		parser.parse_args.assert_called_once_with([])
		args = parser.parse_args.return_value
		args.quiet = False
		main.setup_logging(args)

		Remote.assert_called_once_with(dummy_config())

	def _check_dev_setup(self, parser, Manager, Remote, Generate):
		eq_(parser.add_argument.call_args_list,
			[
				(('-f', '--full'), {'action': 'store_true', 'help': 'Force a complete rebuild on the forge server'}),
			]
		)

		Manager.assert_called_once_with(dummy_config())
		Generate.assert_called_once_with()
		self._check_common_setup(parser, Remote)

	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os.path.isdir')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	@raises(forge.ForgeError)
	def test_user_dir_not_there(self, argparse, isdir, build_config):
		isdir.return_value = False
		build_config.load.return_value = dummy_config()

		main.development_build([])

		isdir.assert_called_once_with(defaults.SRC_DIR)
		ok_(not build_config.called)


	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os.path.isdir')
	@mock.patch('forge.main.shutil')
	@mock.patch('forge.main.Generate')
	@mock.patch('forge.main.Remote')
	@mock.patch('forge.main.Manager')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	def test_dev_no_conf_change(self, argparse, Manager, Remote, Generate, shutil, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		args = parser.parse_args.return_value
		args.full = False
		isdir.return_value = True
		build_config.load.return_value = dummy_config()

		main.development_build([])

		self._check_dev_setup(parser, Manager, Remote, Generate)

		Manager.return_value.templates_for_config.assert_called_once_with(defaults.APP_CONFIG_FILE)
		eq_(shutil.rmtree.call_args_list, [
			(
				('development',),
				{'ignore_errors': True}
			),
			(
				(path.join('development', 'generate_dynamic'),),
				{'ignore_errors': True}
			)
		])
		shutil.copytree.assert_called_once_with(Manager.return_value.templates_for_config.return_value, 'development')
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR)

	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os.path.isdir')
	@mock.patch('forge.main.shutil')
	@mock.patch('forge.main.Generate')
	@mock.patch('forge.main.Remote')
	@mock.patch('forge.main.Manager')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	def test_dev_conf_change(self, argparse, Manager, Remote, Generate, shutil, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		args = parser.parse_args.return_value
		args.full = False
		Manager.return_value.templates_for_config.return_value = None
		Remote.return_value.build.return_value = -1
		isdir.return_value = True
		build_config.load.return_value = dummy_config()

		main.development_build([])

		self._check_dev_setup(parser, Manager, Remote, Generate)
		Manager.return_value.templates_for_config.assert_called_once_with(defaults.APP_CONFIG_FILE)
		Remote.return_value.build.assert_called_once_with(development=True, template_only=True)
		Manager.return_value.fetch_templates.assert_called_once_with(Remote.return_value.build.return_value, clean=False)

		eq_(shutil.rmtree.call_args_list, [
			(
				('development',),
				{'ignore_errors': True}
			),
			(
				(path.join('development', 'generate_dynamic'),),
				{'ignore_errors': True}
			)
		])
		shutil.copytree.assert_called_once_with(Manager.return_value.fetch_templates.return_value, 'development')
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR)

class TestWithErrorHandler(object):
	@mock.patch('forge.main._assert_outside_of_forge_root')
	@mock.patch('forge.main._assert_not_in_subdirectory_of_forge_root')
	@mock.patch('forge.main.sys')
	def test_keyboard_interrupt(self, sys, warn_if_subdir, assert_outside):
		def interrupt():
			raise KeyboardInterrupt()

		main.with_error_handler(interrupt)()
		sys.exit.assert_called_once_with(1)

class TestMain(object):
	@mock.patch('forge.main._dispatch_command')
	@mock.patch('forge.main.argparse')
	def test_if_using_deprecated_command_then_should_warn(self, argparse, dispatch):
		args = mock.Mock()
		args.command = 'create'
		argparse.ArgumentParser.return_value.parse_known_args.return_value = (args, [])

		main._using_deprecated_command('wm-create', 'forge create')
		mock_logging = mock.Mock()
		with mock.patch('forge.main.logging', new=mock_logging):
			main.main()
		warning = mock_logging.getLogger.return_value.warning
		warning.assert_called_with("Using wm-create which is now deprecated and will eventually be unsupported, instead, please use: 'forge create'\n\n")
