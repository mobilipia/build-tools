import logging
import mock
from nose.tools import ok_, eq_

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
def test_gen_options():
	parser = mock.Mock()
	main.add_general_options(parser)
	eq_(parser.add_argument.call_args_list, general_argparse)

@mock.patch('webmynd.main.DirectorySync')
@mock.patch('webmynd.main.Config')
@mock.patch('webmynd.main.argparse')
def test_refresh(argparse, Config, DirectorySync):
	parser = argparse.ArgumentParser.return_value
	main.setup_logging = mock.Mock()
	
	main.refresh()
	
	eq_(parser.add_argument.call_args_list, [
		(('-c', '--config'), {'help': 'your WebMynd configuration file', 'default': defaults.CONFIG_FILE}),
	] + general_argparse)
	ok_(argparse.ArgumentParser.called)
	parser.parse_args.assert_called_once_with()
	args = parser.parse_args.return_value
	main.setup_logging.assert_called_once_with(args)
	Config.assert_called_once_with()
	Config.return_value.parse.called_once_with(args.config)
	config = Config.return_value
	DirectorySync.assert_called_once_with(config)
	DirectorySync.return_value.user_to_target.assert_called_once_with()

@mock.patch('webmynd.main.Remote')
@mock.patch('webmynd.main.Manager')
@mock.patch('webmynd.main.Config')
@mock.patch('webmynd.main.argparse')
def test_init(argparse, Config, Manager, Remote):
	parser = argparse.ArgumentParser.return_value
	main.setup_logging = mock.Mock()
	Remote.return_value.build.return_value = -1
	
	main.init()
	
	eq_(parser.add_argument.call_args_list, [
		(('-c', '--config'), {'help': 'your WebMynd configuration file', 'default': defaults.CONFIG_FILE}),
	] + general_argparse)
	ok_(argparse.ArgumentParser.called)
	parser.parse_args.assert_called_once_with()
	args = parser.parse_args.return_value
	main.setup_logging.assert_called_once_with(args)
	
	Config.assert_called_once_with()
	Config.return_value.parse.called_once_with(args.config)
	Remote.assert_called_once_with(Config.return_value)
	Manager.assert_called_once_with(Config.return_value)
	
	Remote.return_value.get_latest_user_code.assert_called_once_with(defaults.USER_DIR)
	Remote.return_value.build.assert_called_once_with(development=True, template_only=True)
	Manager.return_value.get_templates.assert_called_once_with(-1)

class TestBuild(object):
	def _check_common_setup(self, parser, Config, Remote):
		eq_(parser.add_argument.call_args_list, [
			(('-c', '--config'), {'help': 'your WebMynd configuration file', 'default': defaults.CONFIG_FILE}),
		] + general_argparse)
		parser.parse_args.assert_called_once_with()
		args = parser.parse_args.return_value
		args.quiet = False
		main.setup_logging(args)
	
		Config.assert_called_once_with()
		Config.return_value.parse.called_once_with(args.config)
		Remote.assert_called_once_with(Config.return_value)
		
	def _check_dev_setup(self, parser, Config, Manager, Remote, DirectorySync, Generate):
		Manager.assert_called_once_with(Config.return_value)
		DirectorySync.assert_called_once_with(Config.return_value)
		Generate.assert_called_once_with(Remote.return_value.app_config_file)
		self._check_common_setup(parser, Config, Remote)

	@mock.patch('webmynd.main.shutil')
	@mock.patch('webmynd.main.Generate')
	@mock.patch('webmynd.main.DirectorySync')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Manager')
	@mock.patch('webmynd.main.Config')
	@mock.patch('webmynd.main.argparse')
	def test_dev_no_conf_change(self, argparse, Config, Manager, Remote, DirectorySync, Generate, shutil):
		parser = argparse.ArgumentParser.return_value
		
		main.development_build()
		
		self._check_dev_setup(parser, Config, Manager, Remote, DirectorySync, Generate)
		
		Manager.return_value.templates_for.assert_called_once_with(Remote.return_value.app_config_file)
		shutil.rmtree.assert_called_once_with('development', ignore_errors=True)
		shutil.copytree.assert_called_once_with(Manager.return_value.templates_for.return_value, 'development')
		DirectorySync.return_value.user_to_target.assert_called_once_with(force=True)
		Generate.return_value.all.assert_called_once_with('development', defaults.USER_DIR)
		
	@mock.patch('webmynd.main.shutil')
	@mock.patch('webmynd.main.Generate')
	@mock.patch('webmynd.main.DirectorySync')
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Manager')
	@mock.patch('webmynd.main.Config')
	@mock.patch('webmynd.main.argparse')
	def test_dev_conf_change(self, argparse, Config, Manager, Remote, DirectorySync, Generate, shutil):
		parser = argparse.ArgumentParser.return_value
		Manager.return_value.templates_for.return_value = None
		Remote.return_value.build.return_value = -1
		
		main.development_build()
		
		self._check_dev_setup(parser, Config, Manager, Remote, DirectorySync, Generate)
		
		Manager.return_value.templates_for.assert_called_once_with(Remote.return_value.app_config_file)
		Remote.return_value.build.assert_called_once_with(development=True, template_only=True)
		Manager.return_value.get_templates.assert_called_once_with(-1)
		
		shutil.rmtree.assert_called_once_with('development', ignore_errors=True)
		shutil.copytree.assert_called_once_with(Manager.return_value.get_templates.return_value, 'development')
		DirectorySync.return_value.user_to_target.assert_called_once_with(force=True)
		Generate.return_value.all.assert_called_once_with('development', defaults.USER_DIR)
		
	@mock.patch('webmynd.main.Remote')
	@mock.patch('webmynd.main.Config')
	@mock.patch('webmynd.main.argparse')
	def test_prod(self, argparse, Config, Remote):
		parser = argparse.ArgumentParser.return_value
		Remote.return_value.build.return_value = -1
		
		main.production_build()
		
		self._check_common_setup(parser, Config, Remote)
		
		Remote.return_value.build.assert_called_once_with(development=False, template_only=False)
		Remote.return_value.get_app_config.assert_called_once_with(Remote.return_value.build.return_value)
		Remote.return_value.fetch_unpackaged.assert_called_once_with(Remote.return_value.build.return_value, to_dir='production')