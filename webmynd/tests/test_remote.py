import cookielib
import json
from os import path

import mock
from mock import MagicMock, Mock, patch
from nose.tools import raises, eq_, assert_not_equals, ok_, assert_false

from webmynd.config import Config
from webmynd.remote import Remote
from lib import assert_raises_regexp

class TestRemote(object):
	def setup(self):
		self.test_config = Config._test_instance()
		self.remote = Remote(self.test_config)

class Test_CsrfToken(TestRemote):
	def test_nocsrf(self):
		assert_raises_regexp(Exception, "don't have a CSRF token", self.remote._csrf_token)
	def test_got_csrf(self):
		cookie = Mock()
		cookie.name = 'csrftoken'
		cookie.value = 'csrf value'
		self.remote.cookies = [cookie]
		eq_(self.remote._csrf_token(), 'csrf value')

class TestLatest(TestRemote):
	# latest
	def test_latest(self):
		self.remote._authenticate = Mock()
		get_resp = Mock()
		get_resp.content = json.dumps({'build_id': -1})
		self.remote._get = Mock(return_value=get_resp)
		resp = self.remote.latest()
		eq_(resp, -1)
		self.remote._authenticate.assert_called_once_with( )
		self.remote._get.assert_called_once_with('http://test.webmynd.com/api/app/TEST-UUID/latest/')
		
class TestFetchUnpackaged(TestRemote):
	@patch('webmynd.remote.zipfile')
	@patch('webmynd.remote.path')
	@patch('webmynd.remote.os')
	def test_fetch_unpackaged(self, os, path, zipf):
		output_dir = 'output dir'
		path.abspath.side_effect = lambda x: '/absolute/path/'+x
		path.isdir.return_value = False
		self.remote._authenticate = Mock()
		get_resp = Mock()
		get_resp.content = json.dumps({'unpackaged':{'chrome': '/path/chrome url', 'firefox': '/path/firefox url'}})
		self.remote._get = Mock(return_value=get_resp)
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		
		with mock.patch('__builtin__.open', new=mock_open):
			resp = self.remote.fetch_unpackaged(-1, output_dir)
		
		self.remote._authenticate.assert_called_once_with()
		os.mkdir.assert_called_once_with(output_dir)
		os.chdir.call_args_list[0][0][0] == output_dir
		eq_(manager.write.call_args_list, [((get_resp.content,), {})] * 2)
		ok_(zipf.ZipFile.call_args_list[0][0][0].endswith('chrome url'))
		ok_(zipf.ZipFile.call_args_list[1][0][0].endswith('firefox url'))
		eq_(zipf.ZipFile.return_value.extractall.call_count, 2)
		ok_(resp[0].endswith('chrome'))
		ok_(resp[1].endswith('firefox'))

class TestBuild(TestRemote):
	def setup(self):
		super(TestBuild, self).setup()
		self.remote._authenticate = Mock()
		self.remote.POLL_DELAY = 0.001
		post_resp = Mock()
		get_resp = Mock()
		post_resp.content = json.dumps({'build_id': -1})
		get_resp.content = json.dumps({'build_id': -1, 'state': 'complete', 'log_output': 'test logging'})
		self.remote._post = Mock(return_value=post_resp)
		self.remote._get = Mock(return_value=get_resp)
	def teardown(self):
		self.remote._authenticate.assert_called_once_with()
		
	def test_pending(self):
		states = ['pending', 'working', 'complete']
		def states_effect(*args, **kw):
			mock = Mock()
			mock.content = json.dumps({'build_id': -1, 'state': states.pop(0), 'log_output': 'test logging'})
			return mock
		self.remote._get.side_effect = states_effect
		resp = self.remote.build()
		eq_(resp, -1)
		self.remote._post.assert_called_once_with(
			self.test_config.get('main.server')+'app/TEST-UUID/build/development',
			files=None, data={}
		)
		eq_(self.remote._get.call_args_list,
			[((self.test_config.get('main.server')+'build/-1/detail/',), {})] * 3
		)
	@patch('webmynd.remote.path')
	def test_data(self, mock_path):
		mock_open = MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		app_config = {'test': 'config'}
		manager.read.return_value = json.dumps(app_config)
		mock_path.isfile.return_value = True
		mock_path.isdir.return_value = False
		
		with patch('__builtin__.open', new=mock_open):
			resp = self.remote.build()
		eq_(resp, -1)
		self.remote._post.assert_called_once_with(
			self.test_config.get('main.server')+'app/TEST-UUID/build/development',
			files=None, data={'config': json.dumps(app_config)}
		)
		self.remote._get.assert_called_once_with(self.test_config.get('main.server')+'build/-1/detail/')
		mock_open.assert_called_once_with('app-%s.json' % self.test_config.get('main.uuid'))
	
	@patch('webmynd.remote.path')
	@patch('webmynd.remote.os')
	@patch('webmynd.remote.tarfile')
	def test_user_dir(self, tarfile, os, path):
		mock_open = MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = 'user archive'
		path.isfile.return_value = False
		path.isdir.return_value = True
		
		os.listdir.return_value = ['file.txt']
		os.getcwd.return_value = 'original dir'
		os.remove.side_effect = OSError
		with patch('__builtin__.open', new=mock_open):
			resp = self.remote.build()
			
		tmp_file = mock_open.call_args_list[0][0][0]
		eq_(os.chdir.call_args_list, [(('user',), {}), (('original dir',), {})])
		tarfile.open.assert_called_once_with(tmp_file, mode='w:bz2')
		tarfile.open.return_value.close.assert_called_once_with()
		os.listdir.assert_called_once_with('.')
		tarfile.open.return_value.add.called_once_with('file.txt')
		eq_(len(mock_open.call_args_list), 1)
		os.remove.assert_called_once_with(tmp_file)
	
	def test_fail(self):
		self.remote._get.return_value.content = json.dumps({
			'build_id': -1, 'state': 'aborted', 'log_output': 'test logging'
		})
		
		assert_raises_regexp(Exception, 'build failed', self.remote.build)
		
class Test_Post(TestRemote):
	@patch('webmynd.remote.requests')
	def test_post(self, requests):
		requests.post.return_value.ok = True
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		res = self.remote._post(1, 2, a=3, b=4)
		self.remote._csrf_token.assert_called_once_with()
		requests.post.assert_called_once_with(1, 2, cookies=self.remote.cookies, data={'csrfmiddlewaretoken': 'csrf token'}, a=3, b=4)
		ok_(res is requests.post.return_value)
	@patch('webmynd.remote.requests')
	def test_post_failed_no_msg(self, requests):
		requests.post.return_value.ok = False
		requests.post.return_value.url = 'dummy url'
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'POST to dummy url failed <mock', self.remote._post)
	@patch('webmynd.remote.requests')
	def test_post_failed_msg(self, requests):
		requests.post.return_value.ok = False
		requests.post.return_value.url = 'dummy url'
		requests.post.return_value.status_code = 1000
		requests.post.return_value.content = 'dummy content'
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'POST to dummy url failed: status code', self.remote._post)
	@patch('webmynd.remote.requests')
	def test_post_failed_custom_msg(self, requests):
		requests.post.return_value.ok = False
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'bleurgh', self.remote._post, __error_message='bleurgh')

class Test_Get(TestRemote):
	@patch('webmynd.remote.requests')
	def test_get(self, requests):
		requests.post.return_value.ok = True
		
		res = self.remote._get(1, 2, a=3, b=4)
		requests.get.assert_called_once_with(1, 2, a=3, b=4, cookies=self.remote.cookies, data={})
		ok_(res is requests.get.return_value)
	@patch('webmynd.remote.requests')
	def test_get_failed_no_msg(self, requests):
		requests.get.return_value.ok = False
		requests.get.return_value.url = 'dummy url'
		
		assert_raises_regexp(Exception, 'GET to dummy url failed <mock', self.remote._get)
	@patch('webmynd.remote.requests')
	def test_get_failed_msg(self, requests):
		requests.get.return_value.ok = False
		requests.get.return_value.url = 'dummy url'
		requests.get.return_value.status_code = 1000
		requests.get.return_value.content = 'dummy content'
		
		assert_raises_regexp(Exception, 'GET to dummy url failed: status code', self.remote._get)
	@patch('webmynd.remote.requests')
	def test_get_failed_custom_msg(self, requests):
		requests.get.return_value.ok = False
		
		assert_raises_regexp(Exception, 'bleurgh', self.remote._get, __error_message='bleurgh')

class Test_Authenticate(TestRemote):
	def test_already_authenticated(self):
		self.remote._authenticated = True
		self.remote._authenticate()
	def test_authenticate(self):
		get_mock = Mock()
		post_mock = Mock()
		self.remote._get = get_mock
		self.remote._post = post_mock
		
		self.remote._authenticate()
		self.remote._get.assert_called_once_with(self.test_config.get('main.server')+'auth/hello')
		self.remote._post.assert_called_once_with(self.test_config.get('main.server')+'auth/verify',
			data={
				'username': self.test_config.get('authentication.username'),
				'password': self.test_config.get('authentication.password')
			}
		)
		ok_(self.remote._authenticated)

class TestGetAppConfig(TestRemote):
	def test_normal(self):
		build_config = {'test': 'config'}
		self.remote._authenticate = Mock()
		self.remote._get = Mock()
		# remote server stores config as string, rather than an object, to preserve formatting
		self.remote._get.return_value.content = json.dumps({'config': json.dumps(build_config)})
		mock_open = MagicMock()
		
		with patch('__builtin__.open', new=mock_open):
			filename = self.remote.get_app_config(-1)
		
		self.remote._authenticate.assert_called_once_with()
		self.remote._get.assert_called_once_with(
			self.test_config.get('main.server')+'build/-1/config/')
		
		mock_open.return_value.__enter__.return_value.write.assert_called_once_with(
			json.dumps(build_config, indent=4))
		eq_(filename, 'app-%s.json' % self.test_config.get('main.uuid'))

class TestGetLatestUserCode(TestRemote):
	@patch('webmynd.remote.path')
	def test_already_there(self, path):
		path.exists.return_value = True
		assert_raises_regexp(Exception, 'directory already exists', self.remote.get_latest_user_code)

	@patch('webmynd.remote.tarfile')
	@patch('webmynd.remote.path')
	@patch('webmynd.remote.os')
	def test_normal(self, os, path, tarfile):
		path.exists.return_value = False
		mock_open = MagicMock()
		
		self.remote._authenticate = Mock()
		self.remote._get = Mock()
		self.remote._get.return_value.content = json.dumps({'code_url': 'dummy url'})
		self.remote._get.return_value.read.return_value = 'dummy binary'
		os.getcwd.return_value = 'orig directory'
		
		with patch('__builtin__.open', new=mock_open):
			self.remote.get_latest_user_code('dummy directory')
		
		eq_(len(self.remote._get.call_args_list), 2)
		eq_(self.remote._get.call_args_list, [
			((self.test_config.get('main.server')+'app/'+self.test_config.get('main.uuid')+'/code/',), {}),
			(('dummy url',), {})
		])
		self.remote._authenticate.assert_called_once_with()
		tmp_filename = mock_open.call_args[0][0]
		mock_open.return_value.__enter__.return_value.write.assert_called_once_with('dummy binary')
		os.mkdir.assert_called_once_with('dummy directory')
		eq_(os.chdir.call_args_list, [
			(('dummy directory',), {}), (('orig directory',), {})
		])
		tarfile.open.assert_called_once_with(tmp_filename)
		tarfile.open.return_value.extractall.assert_called_once_with()
		tarfile.open.return_value.close.assert_call_once_with()
		os.remove.assert_called_once_with(tmp_filename)