import cookielib
import json
from os import path

import mock
from mock import MagicMock, Mock, patch
from nose.tools import raises, eq_, assert_not_equals, ok_, assert_false

from webmynd import defaults
from webmynd.remote import Remote, AuthenticationError, RequestError
from webmynd.tests import dummy_config
from lib import assert_raises_regexp

class TestRemote(object):
	def setup(self):
		self.test_config = dummy_config()
		self.remote = Remote(self.test_config)
	
class Test__Init__(object):
	@mock.patch('webmynd.remote.LWPCookieJar')
	@mock.patch('webmynd.remote.os')
	def test_cookies_there(self, os, LWPCookieJar):
		os.path.exists.return_value = True
		os.getcwd.return_value = '/here'
		remote = Remote(dummy_config())
		
		LWPCookieJar.return_value.load.assert_called_once_with()
	@mock.patch('webmynd.remote.LWPCookieJar')
	@mock.patch('webmynd.remote.os')
	def test_cookies_not_there(self, os, LWPCookieJar):
		os.path.exists.return_value = False
		os.getcwd.return_value = '/here'
		
		remote = Remote(dummy_config())
		
		LWPCookieJar.return_value.save.assert_called_once_with()

class Test_Authenticate(TestRemote):
	def test_already_auth(self):
		self.remote._authenticated = True
		self.remote._get = Mock()
		
		self.remote._authenticate()
		
		ok_(not self.remote._get.called)
	def test_have_session(self):
		get_resp = Mock()
		get_resp.content = json.dumps({'result': 'ok', 'loggedin': True})
		self.remote._get = Mock(return_value=get_resp)
		
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			self.remote._authenticate()
		
		ok_(self.remote._authenticated)
		ok_(not mock_raw_input.called)
	@mock.patch('webmynd.remote.getpass')
	def test_real_login(self, getpass):
		get_resp = Mock()
		get_resp.content = json.dumps({'result': 'ok', 'loggedin': False})
		self.remote._get = Mock(return_value=get_resp)
		self.remote._post = Mock()
		
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'raw user input'
		getpass.return_value = 'getpass input'

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			self.remote._authenticate()
		
		ok_(self.remote._authenticated)
		mock_raw_input.assert_called_once_with("Your email address: ")
		getpass.assert_called_once_with()
		
		eq_(2, len(self.remote._get.call_args_list))
		ok_(self.remote._get.call_args_list[0][0][0].endswith('loggedin'))
		ok_(self.remote._get.call_args_list[1][0][0].endswith('hello'))
		
		self.remote._post.assert_called_once_with('https://test.webmynd.com/api/auth/verify', data={'email': 'raw user input', 'password': 'getpass input'})
	@mock.patch('webmynd.remote.getpass')
	def test_non_json_response(self, getpass):
		mock_get = Mock()
		mock_resp = Mock()
		mock_resp.content = "This isn't JSON at all!"
		mock_get.side_effect = RequestError('mock error', mock_resp)
		self.remote._get = mock_get

		assert_raises_regexp(AuthenticationError, "This isn't JSON at all!", self.remote._authenticate)
		
class Test_CsrfToken(TestRemote):
	def test_nocsrf(self):
		cookie = Mock()
		cookie.domain = 'other domain'
		self.remote.cookies = [cookie]
		assert_raises_regexp(Exception, "don't have a CSRF token", self.remote._csrf_token)
	def test_got_csrf(self):
		cookie1 = Mock()
		cookie1.name = 'csrftoken'
		cookie1.value = 'csrf value 1'
		cookie1.domain = 'other domain'
		cookie2 = Mock()
		cookie2.name = 'csrftoken'
		cookie2.value = 'csrf value 2'
		cookie2.domain = 'test.webmynd.com'
		self.remote.cookies = [cookie1, cookie2]
		eq_(self.remote._csrf_token(), 'csrf value 2')

class TestLatest(TestRemote):
	def test_latest(self):
		self.remote._authenticate = Mock()
		get_resp = Mock()
		get_resp.content = json.dumps({'build_id': -1})
		self.remote._get = Mock(return_value=get_resp)
		resp = self.remote.latest()
		eq_(resp, -1)
		self.remote._authenticate.assert_called_once_with( )
		self.remote._get.assert_called_once_with('https://test.webmynd.com/api/app/TEST-UUID/latest/')

class TestCreate(TestRemote):
	def test_normal(self):
		self.remote._authenticate = Mock()
		post_resp = Mock()
		post_resp.content = json.dumps({'result': 'ok', 'uuid': 'SERVER-TEST-UUID'})
		self.remote._post = Mock(return_value=post_resp)
		
		result = self.remote.create('test name')
		
		self.remote._authenticate.assert_called_once_with( )
		self.remote._post.assert_called_once_with('https://test.webmynd.com/api/app/', data={'name': 'test name'})
		eq_(result, 'SERVER-TEST-UUID')

class TestFetchInitial(TestRemote):
	@patch('webmynd.remote.zipfile')
	@patch('webmynd.remote.os')
	@patch('webmynd.remote.shutil')
	def test_normal(self, shutil, os, zipf):
		self.remote._authenticate = Mock()
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		get_resp = Mock()
		get_resp.content = 'zipfile contents'
		self.remote._get = Mock(return_value=get_resp)
		
		with mock.patch('__builtin__.open', new=mock_open):
			result = self.remote.fetch_initial('TEST-UUID')
			
		shutil.move.assert_called_once_with('user', 'src')
		self.remote._get.assert_called_once_with('https://test.webmynd.com/api/app/TEST-UUID/initial_files')
		mock_open.assert_called_once_with('initial.zip', 'wb')
		manager.write.assert_called_once_with('zipfile contents')
		zipf.ZipFile.assert_called_once_with('initial.zip')
		zipf.ZipFile.return_value.extractall.assert_called_once_with()
		os.remove.assert_called_once_with('initial.zip')

class TestFetchPackaged(TestRemote):
	@patch('webmynd.remote.os')
	def test_fetch_packaged(self, os):
		output_dir = 'output dir'
		self.remote._authenticate = Mock()
		
		with patch('webmynd.remote.Remote._fetch_output') as _fetch_output:
			_fetch_output.return_value = ['dummy filename']
			resp = self.remote.fetch_packaged(-1, output_dir)
		
		self.remote._authenticate.assert_called_once_with()
		eq_(os.chdir.call_args_list[-1][0][0], os.getcwd.return_value)
		eq_(_fetch_output.call_args_list[0][0][:2], (-1, output_dir))
		eq_(resp, _fetch_output.return_value)
		
class Test_HandlePackaged(TestRemote):
	def test_normal(self):
		self.remote._handle_packaged('platform', 'filename')
		
class TestFetchUnpackaged(TestRemote):
	# TODO refactor tests to go after _fetch_output directly
	@patch('webmynd.remote.zipfile')
	@patch('webmynd.remote.path')
	@patch('webmynd.remote.os')
	def test_fetch_unpackaged(self, os, path, zipf):
		output_dir = 'output dir'
		path.abspath.side_effect = lambda x: '/absolute/path/'+x
		path.isdir.return_value = False
		self.remote._authenticate = Mock()
		get_resp = Mock()
		get_resp.content = json.dumps({'unpackaged':{'chrome': '/path/chrome url', 'firefox': '/path/firefox url'}, 'log_output': '1\n2'})
		self.remote._get = Mock(return_value=get_resp)
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		
		with mock.patch('__builtin__.open', new=mock_open):
			resp = self.remote.fetch_unpackaged(-1, output_dir)
		
		self.remote._authenticate.assert_called_once_with()
		os.mkdir.assert_called_once_with(output_dir)
		eq_(os.chdir.call_args_list[0][0][0], output_dir)
		eq_(manager.write.call_args_list, [((get_resp.content,), {})] * 2)
		ok_(zipf.ZipFile.call_args_list[0][0][0].endswith('chrome url'))
		ok_(zipf.ZipFile.call_args_list[1][0][0].endswith('firefox url'))
		eq_(zipf.ZipFile.return_value.extractall.call_count, 2)
		ok_(resp[0].endswith('chrome'))
		ok_(resp[1].endswith('firefox'))
		eq_(os.chdir.call_args_list[-1][0][0], os.getcwd.return_value)

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
			'https://test.webmynd.com/api/app/TEST-UUID/build/development',
			files=None, data={}
		)
		eq_(self.remote._get.call_args_list,
			[(('https://test.webmynd.com/api/build/-1/detail/',), {})] * 3
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
			'https://test.webmynd.com/api/app/TEST-UUID/build/development',
			files=None, data={'config': json.dumps(app_config)}
		)
		self.remote._get.assert_called_once_with('https://test.webmynd.com/api/build/-1/detail/')
		# Fails on windows
		#mock_open.assert_called_once_with('user/config.json')
	
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
		eq_(os.chdir.call_args_list, [((defaults.SRC_DIR,), {}), (('original dir',), {})])
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
		
		res = self.remote._post('url', 2, a=3, b=4)
		self.remote._csrf_token.assert_called_once_with()
		requests.post.assert_called_once_with('url', 2, cookies=self.remote.cookies, data={'csrfmiddlewaretoken': 'csrf token'}, a=3, b=4, headers={'REFERER': 'url'})
		ok_(res is requests.post.return_value)
	@patch('webmynd.remote.requests')
	def test_post_failed_no_msg(self, requests):
		requests.post.return_value.ok = False
		requests.post.return_value.url = 'dummy url'
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'POST to dummy url failed <mock', self.remote._post, 'url')
	@patch('webmynd.remote.requests')
	def test_post_failed_msg(self, requests):
		requests.post.return_value.ok = False
		requests.post.return_value.url = 'dummy url'
		requests.post.return_value.status_code = 1000
		requests.post.return_value.content = 'dummy content'
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'POST to dummy url failed: status code', self.remote._post, 'url')
	@patch('webmynd.remote.requests')
	def test_post_failed_custom_msg(self, requests):
		requests.post.return_value.ok = False
		self.remote._csrf_token = Mock(return_value='csrf token')
		
		assert_raises_regexp(Exception, 'bleurgh', self.remote._post, 'url', __error_message='bleurgh')

class Test_Get(TestRemote):
	@patch('webmynd.remote.requests')
	def test_get(self, requests):
		res = self.remote._get('url', 2, a=3, b=4)
		requests.get.assert_called_once_with('url', 2, a=3, b=4, cookies=self.remote.cookies, headers={'REFERER': 'url'})
		ok_(res is requests.get.return_value)
		
	@patch('webmynd.remote.requests')
	def test_get_failed_no_msg(self, requests):
		requests.get.return_value.ok = False
		requests.get.return_value.url = 'dummy url'
		
		assert_raises_regexp(Exception, 'GET to dummy url failed <mock', self.remote._get, 'url')
	@patch('webmynd.remote.requests')
	def test_get_failed_msg(self, requests):
		requests.get.return_value.ok = False
		requests.get.return_value.url = 'dummy url'
		requests.get.return_value.status_code = 1000
		requests.get.return_value.content = 'dummy content'
		
		assert_raises_regexp(Exception, 'GET to dummy url failed: status code', self.remote._get, 'url')
	@patch('webmynd.remote.requests')
	def test_get_failed_custom_msg(self, requests):
		requests.get.return_value.ok = False
		
		assert_raises_regexp(Exception, 'bleurgh', self.remote._get, 'url', __error_message='bleurgh')
		
	@patch('webmynd.remote.requests')
	def test_basic_auth(self, requests):
		self.remote.config['main']['authentication'] = {
			'username': 'test username',
			'password': 'test password',
		}
		self.remote._get('test url')
		requests.get.assert_called_once_with('test url', cookies=self.remote.cookies, auth=('test username', 'test password'), headers={'REFERER': 'test url'})

class Test_CheckVersion(TestRemote):
	def test_update_required(self):
		get_resp = Mock()
		get_resp.content = json.dumps({"url": "http://example.com/forge/upgrade/", "message": "you must upgrade to a newer version of the command-line tools", "upgrade": "required", "result": "ok"})
		self.remote._get = Mock(return_value=get_resp)
		
		assert_raises_regexp(Exception, 'An update to these command line tools is required.', self.remote.check_version)
