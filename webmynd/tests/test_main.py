import logging
import mock
from nose.tools import ok_, eq_, raises

import webmynd
from webmynd.tests import dummy_config, lib
from webmynd import main, defaults
from os import path

@mock.patch('webmynd.main.logging')
def _logging_test(args, level, logging):
	main.setup_logging(args)
	
	logging.basicConfig.assert_called_once_with(level=getattr(logging, level),
		format='[%(levelname)7s] %(message)s')
	logging.getLogger.assert_called_once_with('webmynd.main')


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
]

class TestCreate(object):
	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.argparse')
	def test_normal(self, argparse, Remote, os, build_config):
		parser = argparse.ArgumentParser.return_value
		os.path.exists.return_value = False
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'
		remote = Remote.return_value
		build_config.load.return_value = dummy_config()

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			main.create()
		
		os.path.exists.assert_called_once_with(defaults.SRC_DIR)
		remote.create.assert_called_once_with(mock_raw_input.return_value)
		remote.fetch_initial.assert_called_once_with(remote.create.return_value)

	@mock.patch('webmynd.main.os')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.argparse')
	def test_user_dir_there(self, argparse, Remote, os):
		parser = argparse.ArgumentParser.return_value
		os.path.exists.return_value = True
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'
		remote = Remote.return_value

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			main.create()
		
		os.path.exists.assert_called_once_with(defaults.SRC_DIR)
		ok_(not remote.create.called)
		ok_(not remote.fetch_initial.called)

class TestRun(object):
	@mock.patch('webmynd.main.argparse')
	def test_not_android(self, argparse):
		parser = argparse.ArgumentParser.return_value
		args = mock.Mock()
		args.platform = 'chrome'
		parser.parse_args.return_value = args
		
		main.run()
		
		parser.parse_args.assert_called_once()

	@mock.patch('webmynd.main._check_for_dir')
	@mock.patch('webmynd.main.runAndroid')
	@mock.patch('webmynd.main.argparse')
	def test_found_jdk_and_sdk(self, argparse, runAndroid, _check_for_dir):
		parser = argparse.ArgumentParser.return_value
		args = mock.Mock()
		args.platform = 'android'
		args.device = 'device'
		parser.parse_args.return_value = args

		values = ['jdk', 'sdk']
		def get_dir(*args, **kw):
			return values.pop()

		_check_for_dir.side_effect = get_dir
		
		main.run()
		
		parser.parse_args.assert_called_once()
		runAndroid.assert_called_once_with('sdk', 'jdk', 'device')

class Test_AssertNotSubdirectoryOfForgeRoot(object):
	@mock.patch('webmynd.main.os.getcwd')
	@raises(main.RunningInForgeRoot)
	def test_raises_in_subdirectory(self, getcwd):
		getcwd.return_value = path.join(defaults.FORGE_ROOT, 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

	@mock.patch('webmynd.main.os.getcwd')
	def test_not_confused_by_similar_directory(self, getcwd):
		getcwd.return_value = path.join(defaults.FORGE_ROOT + '-app', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

	@mock.patch('webmynd.main.os.getcwd')
	def test_ok_when_not_in_subdirectory(self, getcwd):
		getcwd.return_value = path.join('not','forge','tools', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root()

class Test_AssertOutsideOfForgeRoot(object):

	@mock.patch('webmynd.main.os')
	@raises(main.RunningInForgeRoot)
	def test_raises_exception_inside_forge_root(self, os):
		os.getcwd = mock.Mock()
		os.getcwd.return_value = defaults.FORGE_ROOT
		main._assert_outside_of_forge_root()

	@mock.patch('webmynd.main.os')
	def test_nothing_happens_outside_of_forge_root(self, os):
		os.getcwd = mock.Mock()
		os.getcwd.return_value = path.join('some', 'other', 'dir')
		main._assert_outside_of_forge_root()


class Test_CheckForDir(object):
	def test_no_dirs(self):
		lib.assert_raises_regexp(Exception, 'dummy', main._check_for_dir, [], 'dummy')
		
	@mock.patch('webmynd.main.os.path.isdir')
	def test_no_slash(self, isdir):
		isdir.return_value = True
		
		result = main._check_for_dir(['dir name'], 'dummy')
		
		eq_(result, 'dir name/')
		isdir.assert_called_once
		
	@mock.patch('webmynd.main.os.path.isdir')
	def test_slash(self, isdir):
		isdir.return_value = True
		
		result = main._check_for_dir(['dir name/'], 'dummy')
		
		eq_(result, 'dir name/')
		isdir.assert_called_once

class TestBuild(object):
	def _check_common_setup(self, parser, Remote):
		parser.parse_args.assert_called_once_with()
		args = parser.parse_args.return_value
		args.quiet = False
		main.setup_logging(args)
	
		Remote.assert_called_once_with(dummy_config())
		
	def _check_dev_setup(self, parser, Manager, Remote, Generate):
		eq_(parser.add_argument.call_args_list,
			[(('-s', '--sdk'), {'help': 'Path to the Android SDK'})] + general_argparse)

		Manager.assert_called_once_with(dummy_config())
		Generate.assert_called_once_with(defaults.APP_CONFIG_FILE)
		self._check_common_setup(parser, Remote)

	def _check_prod_setup(self, parser, Remote):
		eq_(parser.add_argument.call_args_list, general_argparse)

	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.argparse')
	def test_user_dir_not_there(self, argparse, isdir, build_config):
		isdir.return_value = False
		build_config.load.return_value = dummy_config()
		
		main.development_build()

		isdir.assert_called_once_with(defaults.SRC_DIR)
		ok_(not build_config.called)
		
	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.shutil')
	@mock.patch('webmynd.main.Generate')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Manager')
	@mock.patch('webmynd.main.argparse')
	@mock.patch('webmynd.main.time.sleep')
	def test_dev_copy_template_fail(self, sleep, argparse, Manager, Remote, Generate, shutil, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		isdir.return_value = True
		build_config.load.return_value = dummy_config()
		
		def raise_except(*args, **kw):
			raise Exception("Error")

		shutil.copytree.side_effect = raise_except
		
		lib.assert_raises_regexp(Exception, 'Error', main.development_build)
		eq_(sleep.call_count, 5)
		
	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.shutil')
	@mock.patch('webmynd.main.Generate')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Manager')
	@mock.patch('webmynd.main.argparse')
	def test_dev_no_conf_change(self, argparse, Manager, Remote, Generate, shutil, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		isdir.return_value = True
		build_config.load.return_value = dummy_config()
		
		main.development_build()
		
		self._check_dev_setup(parser, Manager, Remote, Generate)
		
		Manager.return_value.templates_for_config.assert_called_once_with(defaults.APP_CONFIG_FILE)
		shutil.rmtree.assert_called_once_with('development', ignore_errors=True)
		shutil.copytree.assert_called_once_with(Manager.return_value.templates_for_config.return_value, 'development')
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR)
		
	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.shutil')
	@mock.patch('webmynd.main.Generate')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Manager')
	@mock.patch('webmynd.main.argparse')
	def test_dev_conf_change(self, argparse, Manager, Remote, Generate, shutil, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		Manager.return_value.templates_for_config.return_value = None
		Remote.return_value.build.return_value = -1
		isdir.return_value = True
		build_config.load.return_value = dummy_config()
		
		main.development_build()
		
		self._check_dev_setup(parser, Manager, Remote, Generate)

		Manager.return_value.templates_for_config.assert_called_once_with(defaults.APP_CONFIG_FILE)
		Remote.return_value.build.assert_called_once_with(development=True, template_only=True)
		Manager.return_value.fetch_templates.assert_called_once_with(Remote.return_value.build.return_value)
		
		shutil.rmtree.assert_called_once_with('development', ignore_errors=True)
		shutil.copytree.assert_called_once_with(Manager.return_value.fetch_templates.return_value, 'development')
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR)
		
	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.argparse')
	def test_prod(self, argparse, Remote, isdir, build_config):
		parser = argparse.ArgumentParser.return_value
		Remote.return_value.build.return_value = -1
		isdir.return_value = True
		build_config.load.return_value = dummy_config()
		
		main.production_build()
		
		self._check_prod_setup(parser, Remote)
		
		Remote.return_value.build.assert_called_once_with(development=False, template_only=False)
		Remote.return_value.fetch_unpackaged.assert_called_once_with(Remote.return_value.build.return_value, to_dir='production')

class TestWithErrorHandler(object):
	@mock.patch('webmynd.main._assert_outside_of_forge_root')
	@mock.patch('webmynd.main._assert_not_in_subdirectory_of_forge_root')
	@mock.patch('webmynd.main.sys')
	def test_keyboard_interrupt(self, sys, warn_if_subdir, assert_outside):
		def interrupt():
			raise KeyboardInterrupt()
		
		main.with_error_handler(interrupt)()
		
		sys.exit.assert_called_once_with(1)
