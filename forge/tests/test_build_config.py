from contextlib import contextmanager
from os.path import join

import mock
from nose.tools import raises, eq_

from forge import build_config, defaults, ForgeError

class TestLoadApp(object):
	def setup(self):
		self.open_file = mock.MagicMock()
		self.opened_file = self.open_file.return_value.__enter__.return_value
		
	@raises(ForgeError)
	def test_malformed_json(self):
		self.opened_file.read.return_value = '[{]'
		
		with mock.patch('forge.build_config.open_file', new=self.open_file):
			build_config.load_app()

	@mock.patch('forge.build_config.path')
	def test_normal_json(self, path):
		path.isfile.return_value = True
		self.opened_file.read.return_value = '{"a": 1, "b": [null, true]}'
		
		with mock.patch('forge.build_config.open_file', new=self.open_file):
			resp = build_config.load_app()
		
		eq_(resp, {"a": 1, "b": [None, True]})

	@raises(IOError)
	def test_no_identity(self):
		@contextmanager
		def open_file_mock(filename, *args, **kw):
			if filename.endswith(defaults.APP_CONFIG_FILE):
				result = mock.Mock()
				result.read.return_value = "{}"
				yield result
			else:
				raise IOError("No such file: {0}".format(filename))
		self.open_file.side_effect = open_file_mock
		
		with mock.patch('forge.build_config.open_file', new=self.open_file):
			resp = build_config.load_app()

	def test_pre_identity_config(self):
		self.identity_file_contents = ''
		@contextmanager
		def open_file_mock(filename, *args, **kw):
			if filename.endswith(defaults.APP_CONFIG_FILE):
				self.opened_file.read.return_value = '{"uuid": "DUMMY_UUID"}'
				yield self.opened_file
			elif filename.endswith(defaults.IDENTITY_FILE):
				def mock_write(contents):
					self.identity_file_contents += contents
				self.opened_file.write = mock_write
				self.opened_file.read.return_value = self.identity_file_contents
				yield self.opened_file
			else:
				raise IOError("No such file: {0}".format(filename))
		self.open_file.side_effect = open_file_mock
		
		with mock.patch('forge.build_config.open_file', new=self.open_file):
			resp = build_config.load_app()
		
		eq_(resp['uuid'], 'DUMMY_UUID')
		eq_(self.open_file.call_args_list, [
			((join(".", defaults.APP_CONFIG_FILE), ), {}),
			((join(".", defaults.IDENTITY_FILE), 'w'), {}),
			((join(".", defaults.IDENTITY_FILE), ), {}),
		])
		

class TestLoadLocal(object):
	@mock.patch('forge.build_config.path.isfile')
	def test_should_return_json_as_dict(self, isfile):
		isfile.return_value = True
		open_file = mock.MagicMock()
		opened_file = open_file.return_value.__enter__.return_value
		opened_file.read.return_value = '{"provisioning_profile": "dummy pp"}'

		with mock.patch('forge.build_config.open_file', new=open_file):
			local_config = build_config.load_local()

		eq_(local_config, {'provisioning_profile': 'dummy pp'})

	def test_if_no_config_file_should_return_empty_dict(self):
		open_file = mock.MagicMock()
		open_file.side_effect = IOError

		with mock.patch('forge.build_config.open_file', new=open_file):
			local_config = build_config.load_local()

		eq_(local_config, {})
