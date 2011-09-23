import mock
from nose.tools import raises, eq_, assert_not_equals, ok_, assert_false
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
		
class TestAll(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		
	@mock.patch('webmynd.generate.shutil')
	@mock.patch('webmynd.generate.tempfile')
	@mock.patch('webmynd.generate.path')
	def test_normal(self, path, tempfile, shutil):
		path.isdir.return_value = True
		self.generate.user = mock.Mock()
		self.generate.firefox = mock.Mock()
		self.generate.chrome = mock.Mock()
		self.generate.android = mock.Mock()
		tmp_dir = tempfile.mkdtemp.return_value
		
		self.generate.all('dummy target dir', 'dummy user dir')

		self.generate.user.assert_called_once_with(tmp_dir, 'dummy user dir')
		self.generate.firefox.assert_called_once_with('dummy target dir', tmp_dir)
		self.generate.chrome.assert_called_once_with('dummy target dir', tmp_dir)
		self.generate.android.assert_called_once_with('dummy target dir', tmp_dir)
		shutil.rmtree.assert_called_once_with(tmp_dir)

class TestUser(object):
	def setup(self):
		self.generate = Generate(path.join(path.dirname(__file__), 'dummy_app_config.json'))
		self.generate.app_config = dummy_config
		
	@mock.patch('webmynd.generate.os')
	def test_normal(self, os):
		os.walk.return_value = (
			('root0', ('dir0-0', 'dir0-1'), ('file0-0.html', 'file0-1.htm', 'file0-2.js', 'file0-3.css', 'file0-4')),
			('root1', (), ('file1-0.txt', 'file1-1')),
			('root2', ('dir2-0', 'dir2-1'), ()),
		)
		
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = 'blah uuid $uuid ${} ${uuid} blah'
		
		with mock.patch('webmynd.generate.codecs.open', new=mock_open):
			self.generate.user('dummy tmp dir', 'dummy user dir')
		
		eq_(manager.read.call_count, 4)
		eq_(manager.write.call_count, 4)
		for call in manager.write.call_args_list:
			# ${uuid} substiturion happened everywhere?
			eq_(call[0][0],
				manager.read.return_value.replace('${uuid}', dummy_config['uuid'])
			)
		f_names = [call[0][0] for call in mock_open.call_args_list]
		# pick every other file name opened because of read then write on same file
		eq_([f_name.split(path.sep)[-1] for f_name in f_names[::2]], ['file0-0.html', 'file0-1.htm', 'file0-2.js', 'file0-3.css'])
		# should alternate read then write
		operations = [call[0][1] for call in mock_open.call_args_list]
		eq_(operations, ['r', 'w'] * 4)
		# should all be utf8
		eq_([call[1]['encoding'] for call in mock_open.call_args_list], ['utf8']*8)
		
		
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
		self.generate.chrome('dummy target dir', 'dummy user dir')
		
		shutil.copy.assert_called_once_with(path.join('dummy target dir', 'chrome', 'common', 'data.js'), path.join('dummy user dir', 'data.js'))
