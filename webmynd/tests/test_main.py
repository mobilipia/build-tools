import logging
import mock
from nose.tools import ok_, eq_

import webmynd
from webmynd.tests import dummy_config
from webmynd import main, defaults

@mock.patch('webmynd.main.logging')
def _logging_test(args, level, logging):
	main.setup_logging(args)
	
	logging.basicConfig.assert_called_once_with(level=getattr(logging, level),
		format='[%(levelname)7s] %(asctime)s -- %(message)s')
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
	(('-q', '--quiet'), {'action': 'store_true'})
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
		
		os.path.exists.assert_called_once_with('user')
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
		
		os.path.exists.assert_called_once_with('user')
		ok_(not remote.create.called)
		ok_(not remote.fetch_initial.called)

class TestBuild(object):
	def _check_common_setup(self, parser, Remote):
		eq_(parser.add_argument.call_args_list, general_argparse)
		parser.parse_args.assert_called_once_with()
		args = parser.parse_args.return_value
		args.quiet = False
		main.setup_logging(args)
	
		Remote.assert_called_once_with(dummy_config())
		
	def _check_dev_setup(self, parser, Manager, Remote, Generate):
		Manager.assert_called_once_with(dummy_config())
		Generate.assert_called_once_with(defaults.APP_CONFIG_FILE)
		self._check_common_setup(parser, Remote)

	@mock.patch('webmynd.main.build_config')
	@mock.patch('webmynd.main.os.path.isdir')
	@mock.patch('webmynd.main.argparse')
	def test_user_dir_not_there(self, argparse, isdir, build_config):
		isdir.return_value = False
		build_config.load.return_value = dummy_config()
		
		main.development_build()

		isdir.assert_called_once_with('user')
		ok_(not build_config.called)
		
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
		Generate.return_value.all.assert_called_once_with('development', defaults.USER_DIR)
		
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
		Generate.return_value.all.assert_called_once_with('development', defaults.USER_DIR)
		
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
		
		self._check_common_setup(parser, Remote)
		
		Remote.return_value.build.assert_called_once_with(development=False, template_only=False)
		Remote.return_value.fetch_packaged.assert_called_once_with(Remote.return_value.build.return_value, to_dir='production')