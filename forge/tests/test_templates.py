import mock
from nose.tools import eq_, ok_
from os import path

from forge.templates import Manager
from forge.tests import dummy_config

class TestNeedNewTemplatesFor(object):
	def setup(self):
		self.manager = Manager(dummy_config())
		
	@mock.patch('forge.templates.path')
	@mock.patch('forge.templates.import_generate_dynamic')
	def test_no_changes(self, import_generate_dynamic, path):
		internal_goals = import_generate_dynamic.return_value.internal_goals
		internal_goals.config_changes_invalidate_templates.return_value = False
		path.isdir.return_value = True

		res = self.manager.need_new_templates_for_config()

		eq_(res, False)

	@mock.patch('forge.templates.path')
	@mock.patch('forge.templates.import_generate_dynamic')
	def test_important_changes(self, import_generate_dynamic, path):
		internal_goals = import_generate_dynamic.return_value.internal_goals
		internal_goals.config_changes_invalidate_templates.return_value = True
		path.isdir.return_value = True
		
		res = self.manager.need_new_templates_for_config()
		
		eq_(res, True)

	@mock.patch('forge.templates.path')
	def test_dir_not_there(self, path):
		path.isdir.return_value = False
		
		res = self.manager.need_new_templates_for_config()
		
		eq_(res, True)

	@mock.patch('forge.templates.path')
	def test_old_config_not_there(self, path):
		path.isfile.return_value = False
		
		res = self.manager.need_new_templates_for_config()
		
		eq_(res, True)

class TestFetchTemplateAppsAndInstructions(object):
	def setup(self):
		self.manager = Manager(dummy_config())
		
	@mock.patch('forge.templates.shutil')
	@mock.patch('forge.templates.Remote')
	@mock.patch('forge.templates.tempfile')
	@mock.patch('forge.templates.import_generate_dynamic')
	def test_no_templates(self, import_generate_dynamic, tempfile, Remote, shutil):
		remote = Remote.return_value
		temp_dir = tempfile.mkdtemp.return_value = 'dummy temp dir'
		
		self.manager.fetch_template_apps_and_instructions(-1)
		
		temp_templates_dir = path.join(temp_dir, '.template')
		temp_instructions_dir = path.join(temp_dir, '.template')

		remote.fetch_unpackaged.assert_called_once_with(-1, to_dir=temp_templates_dir)
		remote.fetch_generate_instructions.assert_called_once_with(temp_instructions_dir)
		
		shutil.rmtree.assert_has_calls(
			[mock.call('.template', ignore_errors=True), mock.call(temp_dir, ignore_errors=True)]
		)

		shutil.move.assert_called_once_with(temp_templates_dir, '.template')
		# ensure invalidation of any cached generate_dynamic module
		import_generate_dynamic.assert_called_once_with(do_reload=True)
