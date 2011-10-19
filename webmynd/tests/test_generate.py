import mock
from nose.tools import raises, eq_, assert_not_equals, ok_, assert_false, assert_raises
from os import path

from lib import assert_raises_regexp
from webmynd.generate import Generate

dummy_config = {
	'uuid': 'TEST-UUID',
	'background_files': ['dummy_file.js', 'http://a.com/a.js'],
}

class TestInit(object):
	def test_normal(self):
		gen = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		eq_(gen.app_config['test'], 'config')
	def test_unicode(self):
		gen = Generate(path.join(path.dirname(__file__), 'dummy_app_config_uni.json'))
		eq_(gen.app_config['test'], u'config\xc5')
	def test_unicode(self):
		assert_raises(UnicodeDecodeError, Generate,
			path.join(path.dirname(__file__), 'dummy_app_config_binary.json'))
		
class TestAll(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		
	@mock.patch('webmynd.generate.shutil')
	@mock.patch('webmynd.generate.tempfile')
	@mock.patch('webmynd.generate.path')
	def test_normal(self, path, tempfile, shutil):
		path.isdir.return_value = True
		self.generate.firefox = mock.Mock()
		self.generate.chrome = mock.Mock()
		self.generate.android = mock.Mock()
		tmp_dir = tempfile.mkdtemp.return_value
		
		self.generate.all(tmp_dir, 'dummy user dir')

		self.generate.firefox.assert_called_once_with(tmp_dir, 'dummy user dir')
		self.generate.chrome.assert_called_once_with(tmp_dir, 'dummy user dir')
		self.generate.android.assert_called_once_with(tmp_dir, 'dummy user dir')

class TestFirefox(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		self.generate.app_config = dummy_config
		
	@mock.patch('webmynd.generate.path.isfile')
	def test_normal(self, isfile):
		isfile.return_value = True
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		
		files = [
			'overlay.js: some text window.__WEBMYND_MARKER=1; other text',
			'dummy_file.js function stuff(things) { here };',
		]
		def open_eff():
			return files.pop(0)
		manager.read.side_effect = open_eff
		
		with mock.patch('webmynd.generate.codecs.open', new=mock_open):
			self.generate.firefox('dummy target dir', 'dummy user dir')
			
		# opening overlay.js
		ok_(mock_open.call_args_list[0][0][0].endswith(path.join('firefox', 'content', 'overlay.js')))
		eq_(mock_open.call_args_list[0][1], {'encoding': 'utf8'})
		
		manager.write.assert_called_once_with('overlay.js: some text \ndummy_file.js function stuff(things) { here }; other text')

class TestChrome(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		self.generate.app_config = dummy_config
	
	@mock.patch('webmynd.generate.shutil')
	def test_normal(self, shutil):
		self.generate._recursive_replace = mock.Mock()
		self.generate.chrome('dummy target dir', 'dummy user dir')
		self.generate._recursive_replace.assert_called_once_with(
				'dummy user dir', 
				path.join('dummy target dir', 'chrome', self.generate.app_config['uuid']),
				('html',),
				"<head>",
				"<head><script src='/webmynd/all.js'></script>"
		)

class TestSafari(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		self.generate.app_config = dummy_config
	
	@mock.patch('webmynd.generate.shutil')
	def test_no_icons(self, shutil):
		self.generate.safari('dummy target dir', 'dummy user dir')
		
		ok_(not shutil.copy.called)

	@mock.patch('webmynd.generate.shutil')
	def test_no_icons(self, shutil):
		saf_config = dummy_config.copy()
		saf_config["icons"] = {"32": "icon32.png"}
		self.generate.app_config = saf_config

		self.generate.safari('dummy target dir', 'dummy user dir')
		
		shutil.copy.assert_called_once_with(
			path.join("dummy user dir","icon32.png"),
			path.join("dummy target dir","webmynd.safariextension", "icon-32.png"),
		)
