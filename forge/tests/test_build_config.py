import mock
from nose.tools import raises, eq_

from forge import build_config, defaults, ForgeError

class TestLoadApp(object):
	def setup(self):
		self.codecs = mock.MagicMock()
		self.codecs_open = self.codecs.open.return_value.__enter__.return_value
		
	def test_argument_is_none(self):
		self.codecs_open.read.return_value = '{}'
		
		with mock.patch('forge.build_config.codecs', new=self.codecs):
			build_config.load_app()
		
		eq_(self.codecs.open.call_args_list, [
			((defaults.APP_CONFIG_FILE, ), dict(encoding="utf8")),
			((defaults.IDENTITY_FILE, ), dict(encoding="utf8")),
		])
	
	@raises(ForgeError)
	def test_malformed_json(self):
		self.codecs_open.read.return_value = '[{]'
		
		with mock.patch('forge.build_config.codecs', new=self.codecs):
			build_config.load_app()
	
	def test_normal_json(self):
		self.codecs_open.read.return_value = '{"a": 1, "b": [null, true]}'
		
		with mock.patch('forge.build_config.codecs', new=self.codecs):
			resp = build_config.load_app()
		
		eq_(resp, {"a": 1, "b": [None, True]})