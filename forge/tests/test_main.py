import os as real_os
import mock
from nose.tools import ok_, eq_, raises

import forge
from forge import tests
from forge import main, defaults
from os import path

@mock.patch('forge.main._setup_logging_to_stdout')
@mock.patch('forge.main._setup_error_logging_to_file')
@mock.patch('forge.main.logging')
def _logging_test(settings, level, logging, _setup_error_logging_to_file, _setup_logging_to_stdout):
	main.setup_logging(settings)

	_setup_error_logging_to_file.assert_called_once_with()
	_setup_logging_to_stdout.assert_called_once_with(getattr(logging, level))

def test_verbose():
	settings = dict(verbose = True)
	_logging_test(settings, 'DEBUG')
def test_quiet():
	settings = dict(quiet = True)
	_logging_test(settings, 'WARNING')
def test_default():
	settings = dict()
	_logging_test(settings, 'INFO')
@raises(main.ArgumentError)
def test_both():
	settings = dict(quiet = True, verbose = True)
	_logging_test(settings, 'DEBUG')

general_argparse = [
	(('-v', '--verbose'), {'action': 'store_true'}),
	(('-q', '--quiet'), {'action': 'store_true'}),
	(('--username', ), {'help': 'username used to login to the forge website'}),
	(('--password', ), {'help': 'password used to login to the forge website'}),
]

class TestCreate(object):
	@mock.patch('forge.main.development_build')
	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os')
	@mock.patch('forge.main.Remote')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main.async.current_call')
	def test_normal(self, current_call, argparse, Remote, mock_os,
			build_config, development_build):
		mock_os.sep = real_os.sep
		parser = argparse.ArgumentParser.return_value
		parser.parse_args.return_value.name = None

		mock_os.path.exists.return_value = False

		call = current_call.return_value
		input = 'user input'
		call.wait_for_response.return_value = {'data': {'name': input}}

		remote = Remote.return_value
		build_config.load.return_value = tests.dummy_config()

		main.create([])

		mock_os.path.exists.assert_called_once_with(defaults.SRC_DIR)
		remote.create.assert_called_once_with(input)
		remote.fetch_initial.assert_called_once_with(remote.create.return_value)
		development_build.assert_called_once_with([])

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
	@mock.patch('forge.main.forge_build')
	@mock.patch('forge.main._assert_have_development_folder')
	@mock.patch('forge.main._assert_have_target_folder')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	def test_not_android(self, _assert_have_target_folder, _assert_have_development_folder, build):
		main.handle_secondary_options('run', ['firefox'])
		main.run([])

		generate_dynamic = build.import_generate_dynamic.return_value
		generate_dynamic.customer_goals.run_app.assert_called_once()

class Test_AssertNotSubdirectoryOfForgeRoot(object):
	@raises(main.RunningInForgeRoot)
	def test_raises_in_subdirectory(self):
		getcwd = path.join(defaults.FORGE_ROOT, 'dummy')
		main._assert_not_in_subdirectory_of_forge_root(getcwd)

	def test_not_confused_by_similar_directory(self):
		getcwd = path.join(defaults.FORGE_ROOT + '-app', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root(getcwd)

	def test_ok_when_not_in_subdirectory(self):
		getcwd = path.join('not','forge','tools', 'dummy')
		main._assert_not_in_subdirectory_of_forge_root(getcwd)

class Test_AssertOutsideOfForgeRoot(object):
	@raises(main.RunningInForgeRoot)
	def test_raises_exception_inside_forge_root(self):
		main._assert_outside_of_forge_root(defaults.FORGE_ROOT)

	def test_nothing_happens_outside_of_forge_root(self):
		main._assert_outside_of_forge_root(path.join('some', 'other', 'dir'))

class TestBuild(object):
	def _check_common_setup(self, parser, Remote):
		parser.parse_args.assert_called_once_with([])
		args = parser.parse_args.return_value
		args.quiet = False
		main.setup_logging(args)

		Remote.assert_called_once_with(tests.dummy_config())

	def _check_dev_setup(self, parser, Manager, Remote, Generate):
		eq_(parser.add_argument.call_args_list,
			[
				(('-f', '--full'), {'action': 'store_true', 'help': 'Force a complete rebuild on the forge server'}),
			]
		)

		Manager.assert_called_once_with(tests.dummy_config())
		Generate.assert_called_once_with()
		self._check_common_setup(parser, Remote)

	@mock.patch('forge.main.build_config')
	@mock.patch('forge.main.os.path.isdir')
	@mock.patch('forge.main.argparse')
	@mock.patch('forge.main._assert_outside_of_forge_root', new=mock.Mock())
	@raises(forge.ForgeError)
	def test_user_dir_not_there(self, argparse, isdir, build_config):
		isdir.return_value = False
		build_config.load.return_value = tests.dummy_config()

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
		Manager.return_value.need_new_templates_for_config.return_value = False
		Remote.return_value.server_says_should_rebuild.return_value = dict(
			should_rebuild = False,
			reason = 'testing',
			stable_platform = 'v1.2',
			platform_state = 'active',
		)
		args.full = False
		build_config.load.return_value = tests.dummy_config()
		build_config.load_app.return_value = tests.dummy_app_config()

		main.development_build([])

		Manager.return_value.need_new_templates_for_config.assert_called_once_with()
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
		shutil.copytree.assert_called_once_with(".template", "development")
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR, extra_args=[])

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
		Manager.return_value.need_new_templates_for_config.return_value = True
		Remote.return_value.server_says_should_rebuild.return_value = dict(
			should_rebuild = False,
			reason = 'testing',
			stable_platform = 'v1.2',
			platform_state = 'active',
		)
		Remote.return_value.build.return_value = {"id": -1}
		isdir.return_value = True
		build_config.load.return_value = tests.dummy_config()
		build_config.load_app.return_value = tests.dummy_app_config()

		main.development_build([])

		Manager.return_value.need_new_templates_for_config.assert_called_once_with()
		Remote.return_value.build.assert_called_once_with(development=True, template_only=True)
		Manager.return_value.fetch_templates.assert_called_once_with(Remote.return_value.build.return_value)

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
		shutil.copytree.assert_called_once_with(".template", 'development')
		Generate.return_value.all.assert_called_once_with('development', defaults.SRC_DIR, extra_args=[])

class TestMain(object):
	@mock.patch('forge.main._dispatch_command')
	@mock.patch('forge.main.argparse')
	def test_if_using_deprecated_command_then_should_warn(self, argparse, dispatch):
		args = mock.Mock()
		args.command = 'create'
		argparse.ArgumentParser.return_value.parse_known_args.return_value = (args, [])

		log = mock.Mock()
		with mock.patch('forge.main.LOG', new=log):
			main._using_deprecated_command('wm-create', 'forge create')
			main.main()
		log.warning.assert_called_with("Using wm-create which is now deprecated and will eventually be unsupported, instead, please use: 'forge create'\n\n")
