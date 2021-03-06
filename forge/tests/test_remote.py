import json
from os import path

import mock
from mock import MagicMock, Mock, patch
from nose.tools import eq_, ok_, assert_raises

from forge import build, lib, remote
from forge.remote import Remote, RequestError
from forge.tests import dummy_config
from lib import assert_raises_regexp

class TestRemote(object):
	def setup(self):
		self.test_config = dummy_config()
		self.remote = Remote(self.test_config)
	
class Test__Init__(object):
	@mock.patch('forge.remote.LWPCookieJar')
	@mock.patch('forge.remote.os')
	def test_cookies_there(self, os, LWPCookieJar):
		os.path.exists.return_value = True
		os.getcwd.return_value = '/here'
		Remote(dummy_config())
		
		LWPCookieJar.return_value.load.assert_called_once_with()
	@mock.patch('forge.remote.LWPCookieJar')
	@mock.patch('forge.remote.os')
	def test_cookies_not_there(self, os, LWPCookieJar):
		os.path.exists.return_value = False
		os.getcwd.return_value = '/here'
		Remote(dummy_config())
		
		LWPCookieJar.return_value.save.assert_called_once_with()

class Test_Authenticate(TestRemote):
	def test_already_auth(self):
		self.remote._authenticated = True
		self.remote._api_get = Mock()
		
		self.remote._authenticate()
		
		ok_(not self.remote._api_get.called)
	def test_have_session(self):
		self.remote._api_get = Mock(return_value={'result': 'ok', 'loggedin': True})
		mock_raw_input = mock.MagicMock()
		mock_raw_input.return_value = 'user input'

		with mock.patch('__builtin__.raw_input', new=mock_raw_input):
			self.remote._authenticate()
		
		ok_(self.remote._authenticated)
		ok_(not mock_raw_input.called)

	@mock.patch('forge.remote.forge.request_username')
	@mock.patch('forge.remote.forge.request_password')
	def test_real_login(self, request_password, request_username):
		self.remote._api_get = Mock(return_value={'result': 'ok', 'loggedin': False})
		self.remote._api_post = Mock()
		request_username.return_value = 'raw user input'
		request_password.return_value = 'getpass input'

		self.remote._authenticate()
		
		ok_(self.remote._authenticated)
		request_username.assert_called_once_with()
		request_username.assert_called_once_with()
		
		eq_(2, len(self.remote._api_get.call_args_list))
		ok_(self.remote._api_get.call_args_list[0][0][0].endswith('loggedin'))
		ok_(self.remote._api_get.call_args_list[1][0][0].endswith('hello'))
		
		self.remote._api_post.assert_called_once_with('auth/verify', data={'email': 'raw user input', 'password': 'getpass input'})
	# @mock.patch('forge.remote.getpass')
	# def test_non_json_response(self, getpass):
	# 	mock_get.side_effect = RequestError('mock error', mock_resp)
	# 	self.remote._api_get = Mock(side_effect=RequestError('mock error', "This isn't JSON at all!"))
	# 	self.remote._authenticate()
	# 	assert_raises_regexp(AuthenticationError, "This isn't JSON at all!", self.remote._authenticate)
		
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
		cookie2.domain = 'test.trigger.io'
		self.remote.cookies = [cookie1, cookie2]
		eq_(self.remote._csrf_token(), 'csrf value 2')

class TestCreate(TestRemote):
	def test_normal(self):
		self.remote._authenticate = Mock()
		self.remote._api_post = Mock(return_value={'result': 'ok', 'uuid': 'SERVER-TEST-UUID'})
		
		result = self.remote.create('test name')
		
		self.remote._authenticate.assert_called_once_with( )
		self.remote._api_post.assert_called_once_with('app/', data={'name': 'test name'})
		eq_(result, 'SERVER-TEST-UUID')

class TestFetchInitial(TestRemote):
	@patch('forge.remote.os')
	@patch('forge.remote.shutil')
	@patch('forge.remote.lib.unzip_with_permissions')
	def test_normal(self, unzip_with_permissions, shutil, os):
		self.remote._authenticate = Mock()
		self.remote._get_file = mock.Mock()

		self.remote.fetch_initial('TEST-UUID')

		destination = path.join('.', 'initial.zip')
		self.remote._get_file.assert_called_once_with(
			'https://test.trigger.io/api/app/TEST-UUID/initial_files/',
			progress_bar_title='Fetching initial files',
			write_to_path=destination
		)
		
		unzip_with_permissions.assert_called_once_with(destination, '.')
		os.remove.assert_called_once_with(destination)

class TestFetchUnpackaged(TestRemote):

	# TODO refactor tests to go after _fetch_output directly
	@patch('forge.remote.path.isdir', new=mock.Mock(return_value=False))
	@patch('forge.remote.path.abspath', new=mock.Mock(side_effect=lambda x: '/absolute/path/'+x))
	@patch('forge.remote.os.remove')
	@patch('forge.remote.os.mkdir')
	@patch('forge.remote.lib.unzip_with_permissions')
	def test_fetch_unpackaged(self, unzip_with_permissions, mkdir, remove):
		cd = mock.MagicMock()
		self.remote._authenticate = Mock()
		self.remote._get_file = mock.Mock()

		build_dict = {
			'id': -1,
			'unpackaged': {
				'chrome': '/path/chrome url',
				'firefox': '/path/firefox url'
			},
			'log_output': '1\n2'
		}
		self.remote._api_get = Mock(
			return_value=build_dict,
		)

		output_dir = 'output dir'

		with patch('forge.remote.lib.cd', new=cd):
			# what does -1 signify here?
			resp = self.remote.fetch_unpackaged(
					build_dict, output_dir)

		self.remote._authenticate.assert_called_once_with()
		mkdir.assert_called_once_with(output_dir)
		cd.assert_called_once_with(output_dir)

		#eq_(self._get_file.call_args_list, [
		#
		#])

		eq_(unzip_with_permissions.call_args_list, [
			(("chrome url", ), {}),
			(("firefox url", ), {}),
		])

		# remove called?

		ok_(resp[0].endswith('chrome'))
		ok_(resp[1].endswith('firefox'))

class TestBuild(TestRemote):
	def setup(self):
		super(TestBuild, self).setup()
		self.remote._authenticate = Mock()
		self.remote.POLL_DELAY = 0.001
		self.remote._api_post = Mock(return_value={
			'id': -1, "state": "pending"
		})
		self._complete_build_dict = {
			'id': -1, 'state': 'complete',
			'log_output': 'test logging'
		}
		self.remote._api_get = Mock(
				return_value=self._complete_build_dict)
	def teardown(self):
		self.remote._authenticate.assert_called_once_with()
		
	@patch('forge.remote.os.listdir')
	@patch('forge.remote.path')
	@patch('forge.remote.build_config')
	def test_pending(self, build_config, path, listdir):
		'''a new build should not be started if a pending one
		exists, and we should poll until that build completes /
		aborts
		'''
		app_config = {"uuid": "TEST-UUID"}
		build_config.load_app.return_value = app_config
		states = ['pending', 'working', 'complete']
		path.isfile.return_value = False
		path.isdir.return_value = True
		cd = MagicMock()
		listdir.return_value = []

		def states_effect(*args, **kw):
			return {'id': -1, 'state': states.pop(0), 'log_output': 'test logging'}
		self.remote._api_get.side_effect = states_effect
		
		with patch('forge.remote.lib.cd', new=cd):
			resp = self.remote.build(template_only=True)
		
		# check that it only returns once we get to complete state
		eq_(resp, {'id': -1, 'state': 'complete',
			'log_output': 'test logging'})
		self.remote._api_post.assert_called_once_with(
			'app/TEST-UUID/template',
			data={"config": '{"uuid": "TEST-UUID"}'}
		)
		eq_(self.remote._api_get.call_args_list,
			[(('build/-1/detail/',), {})] * 3
		)
	@patch('forge.remote.os.listdir')
	@patch('forge.remote.path')
	@patch('forge.remote.build_config')
	def test_data(self, build_config, mock_path, listdir):
		app_config = {'uuid': 'TEST-UUID', 'test': 'config'}
		build_config.load_app.return_value = app_config
		mock_path.isfile.return_value = True
		mock_path.isdir.return_value = True
		
		resp = self.remote.build(template_only=True)

		# Q: what does -1 signify here?
		# A: it's the build id set up in our mock API return
		# value in TestBuild.setup
		eq_(resp, self._complete_build_dict)
		self.remote._api_post.assert_called_once_with(
			'app/TEST-UUID/template',
			data={'config': json.dumps(app_config)}
		)
		self.remote._api_get.assert_called_once_with('build/-1/detail/')
	
	@patch('forge.remote.path')
	@patch('forge.remote.os')
	@patch('forge.remote.lib.human_readable_file_size')
	@patch('forge.remote.build_config')
	def test_user_dir(self, build_config, filesize, os, path):
		app_config = {"uuid": "TEST-UUID"}
		build_config.load_app.return_value = app_config
		path.isfile.return_value = False
		path.isdir.return_value = True
		cd = MagicMock()

		os.listdir.return_value = ['file.txt']

		with patch('forge.remote.lib.cd', new=cd):
			resp = self.remote.build()
				
		eq_(resp, self._complete_build_dict)
		self.remote._api_post.assert_called_once_with('app/TEST-UUID/template',
			data={"config": '{"uuid": "TEST-UUID"}'}
		)
		
	@patch('forge.remote.path')
	@patch('forge.remote.build_config')
	def test_fail(self, build_config, path):
		app_config = {'uuid': 'DUMMY_UUID', 'test': 'config'}
		build_config.load_app.return_value = app_config
		path.isfile.return_value = False
		path.isdir.return_value = True
		self.remote._api_get.return_value = {'build_id': -1, 'state': 'aborted', 'log_output': 'test logging'}
		
		assert_raises_regexp(Exception, 'build failed', self.remote.build, template_only=True)
		
class Test_CheckVersion(TestRemote):
	def test_update_required(self):
		self.remote._api_get = Mock(return_value={"url": "http://example.com/forge/upgrade/", "message": "you must upgrade to a newer version of the command-line tools", "upgrade": "required", "result": "ok"})
		
		assert_raises(remote.UpdateRequired, self.remote.check_version)

class TestGenerateInstructions(TestRemote):
	@patch('forge.remote.forge_build')
	@patch('forge.remote.os')
	@patch('forge.remote.build_config')
	@patch('forge.remote.shutil')
	@patch('forge.remote.lib.unzip_with_permissions')
	def test_normal(self, unzip_with_permissions, shutil, build_config, os,
			forge_build):
		build_config.load_app.return_value = {"platform_version": "v1.3"}
		cd = mock.MagicMock()
		self.remote._authenticate = Mock()
		self.remote._get_file = mock.Mock()

		with mock.patch('forge.lib.cd', new=cd):
			self.remote.fetch_generate_instructions(
				to_dir='my/path'
			)
		
		self.remote._get_file.assert_called_once_with(
			'https://test.trigger.io/api/platform/v1.3/generate_instructions/',
			'instructions.zip'
		)

		cd.assert_called_once_with('my/path')
		unzip_with_permissions.assert_called_once_with('instructions.zip')

class TestCheckApiResponseForError(TestRemote):
	
	'''Check an API response from the website to see if there was an error. Checks for one of the following:

	No status code, as in, no valid response from the server.
	
	HTTP status code is not 200 but get a JSON response
	HTTP status code is not 200 and the response is not a valid JSON response

	Code 200 with a valid JSON response and the 'result' property is set to 'error'
	Code 200 with no JSON response

	:param url: The API url used in the request
	:param method: The HTTP method used in the request (e.g. GET or POST)
	:param resp: The response from the API call
	:raises: RequestException if the response is an error or malformed
'''
	def test_500_valid_json(self):
		resp = mock.Mock()
		resp.content = json.dumps({'result': 'error', 'text': 'Internal error: testing'})
		resp.status_code = 500
		resp.ok = False
		
		assert_raises_regexp(RequestError, 'Internal error: testing',
			remote._check_api_response_for_error,
			'http://dummy.trigger.io/',
			'GET',
			resp,
		)
	def test_500_invalid_json(self):
		resp = mock.Mock()
		resp.content = "wat!["
		resp.status_code = 500
		resp.ok = False
		
		assert_raises_regexp(RequestError, 'GET to http://dummy.trigger.io/ failed',
			remote._check_api_response_for_error,
			'http://dummy.trigger.io/',
			'GET',
			resp,
		)
	def test_200_error(self):
		resp = mock.Mock()
		resp.content = json.dumps({'result': 'error', 'text': 'Internal error: testing'})
		resp.status_code = 200
		resp.ok = True
		
		assert_raises_regexp(RequestError, 'Internal error: testing',
			remote._check_api_response_for_error,
			'http://dummy.trigger.io/',
			'GET',
			resp,
		)
	def test_200_invalid_json(self):
		resp = mock.Mock()
		resp.content = "wat!["
		resp.status_code = 200
		resp.ok = True
		
		assert_raises_regexp(RequestError, 'Server meant to respond with JSON, but response content was',
			remote._check_api_response_for_error,
			'http://dummy.trigger.io/',
			'GET',
			resp,
		)
	def test_no_status_code(self):
		resp = mock.Mock()
		resp.status_code = None
		resp.ok = False
		
		assert_raises_regexp(RequestError, 'got no response',
			remote._check_api_response_for_error,
			'http://dummy.trigger.io/',
			'GET',
			resp,
		)

class TestShouldRebuild(TestRemote):
	@patch('forge.remote.build_config')
	@patch('forge.remote.lib.platform_changeset')
	def test_rebuild_required(self, platform_changeset, build_config):
		self.remote._api_get = Mock(return_value={
			'result': 'ok', 'should_rebuild': True,
			'reason': 'dummy reason'})
		self.remote._authenticate = Mock()
		app_config = {'platform_version': 'v1.2',
				'uuid': 'TEST-UUID'}
		build_config.load_app.return_value = app_config
		platform_changeset.return_value = '000000000000'

		eq_(self.remote.server_says_should_rebuild(),
				self.remote._api_get.return_value)

		self.remote._api_get.assert_called_once_with("app/TEST-UUID/should_rebuild",
				params=dict(
					platform_version=app_config.get('platform_version'),
					platform_changeset=lib.platform_changeset(),
					targets=",".join(build._enabled_platforms('development')),
				)
		)

	@patch('forge.remote.build_config')
	@patch('forge.remote.lib.platform_changeset')
	def test_rebuild_not_required(self, platform_changeset, build_config):
		self.remote._api_get = Mock(return_value={'result': 'ok', 'should_rebuild': False, 'reason': 'dummy reason'})
		self.remote._authenticate = Mock()
		app_config = {'platform_version': 'v1.2', 'uuid': 'TEST-UUID'}
		build_config.load_app.return_value = app_config
		platform_changeset.return_value = '000000000000'

		eq_(self.remote.server_says_should_rebuild(), 
				self.remote._api_get.return_value)

		self.remote._api_get.assert_called_once_with("app/TEST-UUID/should_rebuild",
				params = dict(
					platform_version=app_config.get('platform_version'),
					platform_changeset=lib.platform_changeset(),
					targets=",".join(build._enabled_platforms('development')),
				)
		)
