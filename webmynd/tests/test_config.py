try:
	import json
except ImportError:
	import simplejson as json
	
from nose.tools import eq_, raises
import mock

import webmynd
from lib import assert_raises_regexp
from webmynd import config

class TestConfig(object):
	def setup(self):
		self.config = config.Config._test_instance()
		
	@mock.patch('webmynd.config.path')
	def test_parse(self, mock_path):
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = json.dumps(config.Config.DUMMY_CONFIG)
		mock_path.isfile.return_value = True
		
		with mock.patch('__builtin__.open', new=mock_open):
			self.config.parse('dummy filename')
		mock_open.assert_called_once_with('dummy filename')
		eq_(self.config.get('authentication.password'),
			config.Config.DUMMY_CONFIG['authentication']['password'])
		eq_(self.config.build_config_file, 'dummy filename')
		
	@mock.patch('webmynd.config.path')
	def test_no_file(self, mock_path):
		mock_path.isfile.return_value = False
		assert_raises_regexp(Exception, '^Configuration file', self.config.parse, 'dummy filename')
		
	@mock.patch('webmynd.config.path')
	def test_no_default_file(self, mock_path):
		mock_path.isfile.return_value = False
		assert_raises_regexp(Exception, 'default configuration file', self.config.parse, webmynd.defaults.CONFIG_FILE)
	
	def test_get(self):
		eq_(self.config.get('main.uuid'), config.Config.DUMMY_CONFIG['main']['uuid'])
	def test_get_default(self):
		eq_(self.config.get('main.non_existent', 'default value'), 'default value')
	@raises(KeyError)
	def test_get_no_default(self):
		self.config.get('main.non_existent')
		
	@mock.patch('webmynd.config.path')
	def test_verify(self, path):
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = '{}'
		path.isfile.return_value = True
		
		with mock.patch('__builtin__.open', new=mock_open):
			self.config.verify('dummy filename')
		mock_open.assert_called_once_with('dummy filename')
		path.isfile.assert_called_once_with('dummy filename')		
	@mock.patch('webmynd.config.path')
	def test_verify_no_file(self, path):
		path.isfile.return_value = False
		assert_raises_regexp(IOError, 'not a valid file', self.config.verify, 'dummy filename')
		
	@raises(ValueError)
	@mock.patch('webmynd.config.path')
	def test_verify_bad_json(self, path):
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = '{[}'
		path.isfile.return_value = True
		
		with mock.patch('__builtin__.open', new=mock_open):
			self.config.verify('dummy filename')