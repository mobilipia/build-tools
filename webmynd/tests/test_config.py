try:
	import json
except ImportError:
	import simplejson as json
	
from nose.tools import eq_, raises
import mock

import webmynd
from webmynd import config

class TestConfig(object):
	def setup(self):
		self.config = config.BuildConfig._test_instance()
		
	@mock.patch('webmynd.config.path')
	def test_parse(self, mock_path):
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = json.dumps(config.BuildConfig.DUMMY_CONFIG)
		mock_path.isfile.return_value = True
		
		with mock.patch('__builtin__.open', new=mock_open):
			self.config.parse('dummy filename')
		mock_open.assert_called_once_with('dummy filename')
		mock_path.assert_called_once()
		eq_(self.config.get('authentication.password'),
			config.BuildConfig.DUMMY_CONFIG['authentication']['password'])
		
	@raises(Exception)
	@mock.patch('webmynd.config.path')
	def test_no_file(self, mock_path):
		mock_path.isfile.return_value = False
		self.config.parse('dummy filename')
		
	@raises(Exception)
	@mock.patch('webmynd.config.path')
	def test_no_default_file(self, mock_path):
		mock_path.isfile.return_value = False
		self.config.parse(webmynd.defaults.CONFIG_FILE)
	
	def test_get(self):
		eq_(self.config.get('main.uuid'), config.BuildConfig.DUMMY_CONFIG['main']['uuid'])
	def test_get_default(self):
		eq_(self.config.get('main.non_existent', 'default value'), 'default value')
	@raises(KeyError)
	def test_get_no_default(self):
		self.config.get('main.non_existent')