'Operations which require involvement of the remote Forge build servers'
from cookielib import LWPCookieJar
from StringIO import StringIO
import json
import logging
import os
from os import path
import shutil
import time
import urlparse
from urlparse import urljoin, urlsplit
from threading import Lock
import errno
import traceback

import requests

import forge
from forge import build as forge_build, build_config, defaults
from forge import ForgeError, lib

LOG = logging.getLogger(__name__)

cookie_lock = Lock()

class RequestError(ForgeError):
	def __init__(self, response, message, errors=None):
		ForgeError.__init__(self, message)
		self.response = response
		self.errors = errors

	def extra(self):
		return dict(
			content=self.response.content,
			errors=self.errors,
		)

class FormError(ForgeError):
	def __init__(self, errors, *args, **kw):
		ForgeError.__init__(self, *args, **kw)
		self.errors = errors

	def extra(self):
		return dict(
			errors=self.errors
		)

def _check_api_response_for_error(url, method, resp, error_message=None):
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
	if error_message is None:
		error_message = method +' to %(url)s failed: status code %(status_code)s\n%(content)s'

	LOG.debug("Checking API response for success or error")

	error_template = "Forge API call to {url} went wrong: {reason}"

	if not resp.ok:
		if resp.status_code is None:
			raise RequestError(resp, "Request to {url} got no response".format(url=url))
		try:
			content_dict = json.loads(resp.content)
			if content_dict['result'] == 'error':
				reason = content_dict.get('text', 'Unknown error')
				errors = content_dict.get('errors')
				error_message = error_template.format(url=url, reason=reason)
				raise RequestError(resp, error_message, errors=errors)

		except ValueError:
			try:
				msg = error_message % resp.__dict__
			except KeyError: # in case error_message is looking for something resp doesn't have
				msg = method+' to %s failed: %s' % (
					url,
					str(resp),

					# XXX: seems way too chatty, would be good to have as debug output though
					#getattr(resp, 'content', 'unknown error')[:25]
				)
			raise RequestError(resp, msg)
	else:
		try:
			content_dict = json.loads(resp.content)
			if content_dict['result'] == 'error':
				reason = content_dict.get('text', 'unknown error')
				errors = content_dict.get('errors')
				error_message = error_template.format(reason=reason, url=url)
				raise RequestError(resp, error_message, errors=errors)

		except ValueError:
			reason = 'Server meant to respond with JSON, but response content was: %s' % resp.content
			error_message = error_template.format(reason=reason, url=url)
			raise RequestError(resp, reason)


def _check_response_for_error(url, method, resp):
	if not resp.ok:
		raise RequestError(resp, "Request to {url} went wrong, error code: {code}".format(url=url, code=resp.status_code))

def _cookies_for_domain(domain, cookies):
	return dict((c.name, c.value) for c in cookies if c.domain == domain)

class UpdateRequired(Exception):
	pass

class Remote(object):
	'Wrap remote operations'
	POLL_DELAY = 10

	def __init__(self, config):
		'Start new remote Forge builds'
		self.session = requests.session()
		self.config = config
		cookie_path = self._path_to_cookies()
		self.cookies = LWPCookieJar(cookie_path)
		cookie_lock.acquire()
		if not os.path.exists(cookie_path):
			self.cookies.save()
		else:
			self.cookies.load()
		cookie_lock.release()
		self._authenticated = False

	def _path_to_cookies(self):
		return path.join(defaults.FORGE_ROOT, 'cookies.txt')

	@property
	def server(self):
		'The URL of the build server to use (default https://trigger.io/api/)'
		return self.config.get('main', {}).get('server', 'https://trigger.io/api/')

	@property
	def hostname(self):
		'The hostname of the build server'
		return urlparse.urlparse(self.server).hostname

	def _csrf_token(self):
		'''Return the server-negotiated CSRF token, if we have one

		:raises Exception: if we don't have a CSRF token
		'''
		for cookie in self.cookies:
			if cookie.domain in self.server and cookie.name == 'csrftoken':
				return cookie.value
		else:
			raise Exception("We don't have a CSRF token")

	def __get_or_post(self, url, *args, **kw):
		'''Expects ``__method`` entry in :param:`**kw`
		'''
		method = kw['__method']
		del kw['__method']

		kw['verify'] = True

		if method == "POST":
			# must have CSRF token
			data = kw.get("data", {})
			data['build_tools_version'] = forge.get_version()
			data["csrfmiddlewaretoken"] = self._csrf_token()
			kw["data"] = data
		kw['cookies'] = _cookies_for_domain(self.hostname, self.cookies)
		kw['headers'] = {'REFERER': url}

		if self.config.get('main', {}).get('authentication'):
			if urlparse.urlparse(url).hostname == self.hostname:
				kw['auth'] = (
					self.config['main']['authentication'].get('username'),
					self.config['main']['authentication'].get('password')
				)

		if self.config.get('main', {}).get('proxies'):
			kw['proxies'] = self.config['main']['proxies']

		LOG.debug('{method} {url}'.format(method=method.upper(), url=url))
		resp = getattr(self.session, method.lower())(url, *args, **kw)

		lib.load_cookies_from_response(resp, self.cookies)
		cookie_lock.acquire()
		self.cookies.save()
		cookie_lock.release()
		# XXX: response is definitely json at this point?
		# guaranteed if we're only making calls to the api
		return resp

	def _api_post(self, url, *args, **kw):
		'''Make a POST request.

		:param url: see :module:`requests`
		:param *args: see :module:`requests`
		'''
		kw['__method'] = 'POST'

		absolute_url = urljoin(self.server, url)
		resp = self.__get_or_post(absolute_url, *args, **kw)
		_check_api_response_for_error(url, 'POST', resp)

		return json.loads(resp.content)

	def _api_get(self, url, *args, **kw):
		'''Make a GET request.

		:param url: see :module:`requests`
		:param *args: see :module:`requests`
		'''
		kw['__method'] = 'GET'
		absolute_url = urljoin(self.server, url)
		resp = self.__get_or_post(absolute_url, *args, **kw)
		_check_api_response_for_error(url, 'GET', resp)

		return json.loads(resp.content)

	def _get(self, url, *args, **kw):
		'''Make a GET request.

		:param url: see :module:`requests`
		:param *args: see :module:`requests`
		'''
		kw['__method'] = 'GET'
		resp = self.__get_or_post(url, *args, **kw)
		_check_response_for_error(url, 'GET', resp)
		return resp

	def _post(self, url, *args, **kw):
		'''Make a GET request.

		:param url: see :module:`requests`
		:param *args: see :module:`requests`
		'''
		kw['__method'] = 'POST'
		resp = self.__get_or_post(url, *args, **kw)
		_check_response_for_error(url, 'POST', resp)
		return resp

	def _authenticate(self):
		'''Authentication handshake with server (if we haven't already)
		'''
		if self._authenticated:
			LOG.debug('already authenticated - continuing')
			return

		resp = self._api_get('auth/loggedin')
		if resp.get('loggedin'):
			self._authenticated = True
			LOG.debug('already authenticated via cookie - continuing')
			return

		email = forge.request_username()
		password = forge.request_password()

		self.login(email, password)

	def list_plugins(self):
		self._authenticate()
		return self._api_get('plugin/')

	def list_builds_for_plugin(self, plugin_id):
		self._authenticate()
		return self._api_get('plugin/%s/build/' % plugin_id)

	def list_builds_for_team(self):
		return self._api_get('plugin_build/')

	def create_plugin(self, plugin_name):
		self._authenticate()
		self._api_post('plugin/', data={
			'name': plugin_name
		})

	def create_plugin_build(self, plugin_id, version, description, files_to_upload):
		with FilesUploadDict(**files_to_upload) as upload_dict:
			self._authenticate()
			self._api_post('multiple_plugin_build/', data={
				'plugin_id': plugin_id,
				'version': version,
				'description': description
			}, files=upload_dict)

	def list_apps(self):
		self._authenticate()
		return self._api_get('app/')

	def create(self, name):
		self._authenticate()

		data = {
			'name': name
		}
		LOG.info('Registering new app "{name}" with {hostname}...'.format(
			name=name,
			hostname=self.hostname,
		))
		return self._api_post('app/', data=data)['uuid']

	def check_version(self):
		result = self._api_get(
			'version_check/{version}/'.format(version=forge.get_version().replace('.','/'))
		)

		if result['result'] == 'ok':
			if 'upgrade' in result:
				LOG.info('Update result: %s' % result['message'])
			else:
				LOG.debug('Update result: %s' % result['message'])

			if result.get('upgrade') == 'required':
				raise UpdateRequired()
		else:
			LOG.info('Upgrade check failed.')

	# TODO: currently this method seems to corrupt zip files downloaded,
	# not sure why.
	def _get_file_with_progress_bar(self, response, write_to_path, progress_bar_title):
		if progress_bar_title is None:
			progress_bar_title = 'Download'
		content_length = response.headers.get('content-length')
		message = 'Fetching ({content_length}) into {out_file}'.format(
			content_length=content_length,
			out_file=write_to_path
		)
		LOG.debug(message)

		with lib.ProgressBar(progress_bar_title) as bar:

			bytes_written = 0
			with open(write_to_path, 'wb') as write_to_file:
				# TODO: upgrade requests, use Response.iter_content
				for chunk in response.iter_content(chunk_size=102400):
					if content_length:
						content_length = int(content_length)
						write_to_file.write(chunk)
						bytes_written += len(chunk)
						fraction_complete = float(bytes_written) / content_length
						bar.progress(fraction_complete)

					write_to_file.write(chunk)

	def _get_file(self, url, write_to_path, progress_bar_title=None):
		response = self._get(url)
		try:
			content_length = float(response.headers.get('Content-length'))
		except Exception:
			content_length = None

		# TODO: fix usage of iter_content for fetching files with progress bar.
		if False and content_length:
			self._get_file_with_progress_bar(response, write_to_path, progress_bar_title)
		else:
			with open(write_to_path, 'wb') as write_to_file:
				write_to_file.write(response.content)

	def fetch_initial(self, uuid, app_path="."):
		'''Retrieves the initial project template

		:param uuid: project uuid
		'''
		LOG.info('Fetching initial project template')
		self._authenticate()

		initial_zip_filename = path.join(app_path, 'initial.zip')

		self._get_file(
			urljoin(self.server, 'app/{uuid}/initial_files/'.format(uuid=uuid)),
			write_to_path=initial_zip_filename,
			progress_bar_title='Fetching initial files'
		)
		lib.unzip_with_permissions(initial_zip_filename, app_path)
		LOG.debug('Extracted initial project template')

		os.remove(initial_zip_filename)
		LOG.debug('Removed downloaded file "%s"' % initial_zip_filename)

	def _handle_unpackaged(self, platform, filename):
		'''De-compress a built output tree.

		:param platform: e.g. "chrome", "ios" - we expect the contents of the ZIP file to
			contain a directory named after the relevant platform
		:param filename: the ZIP file to extract
		'''
		shutil.rmtree(platform, ignore_errors=True)
		LOG.debug('removed "%s" directory' % platform)

		lib.unzip_with_permissions(filename)
		LOG.debug('Extracted unpackaged build for %s' % platform)

		os.remove(filename)
		LOG.debug('removed downloaded file "%s"' % filename)

	def fetch_unpackaged(self, build, to_dir, target):
		'''Retrieves the unpackaged artefacts for a particular build.
		
		:param build: the build to fetch
		:param to_dir: directory that will hold all the unpackged build trees
		'''
		LOG.info('Fetching Forge templates for %s into "%s"' % (build["id"], to_dir))
		self._authenticate()
		
		filenames = []
		if not path.isdir(to_dir):
			LOG.debug('Creating output directory "%s"' % to_dir)
			os.mkdir(to_dir)
			
		with lib.cd(to_dir):
			location = build['file_output']

			filename = urlsplit(location).path.split('/')[-1]
			
			LOG.debug('writing %s to %s' % (location, path.abspath(filename)))
			self._get_file(
				location,
				write_to_path=filename,
				progress_bar_title=target,
			)
			
			self._handle_unpackaged(target, filename)
			
			filenames.append(path.abspath(target))
		
		LOG.debug('Fetched build into "%s"' % '", "'.join(filenames))
		return filenames

	def fetch_generate_instructions(self, to_dir):
		'''Retreive the generation instructions for our current environment.

		Rather than hard-coding these instructions - how to inject customer
		code into the apps - they are loaded dynamically from the server to
		allow for different platforms versions to work with a larger number
		of build-tools versions.

		:param to_dir: where the instructions will be put
		'''
		self._authenticate()

		platform_version = build_config.load_app()['platform_version']
		temp_instructions_file = 'instructions.zip'

		LOG.info("Fetching generation instructions for {platform_version} "
				"into \"{to_dir}\"".format(**locals()))

		try:
			# ensure generate_dynamic dir is there before extracting instructions into it
			if not path.isdir(to_dir):
				os.makedirs(to_dir)

			with lib.cd(to_dir):
				self._get_file(
					urljoin(
						self.server,
						'platform/{platform_version}/generate_instructions/'
						.format(platform_version=platform_version)),
					temp_instructions_file
				)
				lib.unzip_with_permissions(temp_instructions_file)

		finally:
			if path.isfile(path.join(to_dir, temp_instructions_file)):
				os.remove(path.join(to_dir, temp_instructions_file))

		return to_dir

	def _request_development_build(self, config, target, id=None):
		data = {}
		app_config = config

		data['config'] = json.dumps(app_config)
		data['target'] = target
		if not id is None:
			data['id'] = id
		
		url = 'app/{uuid}/build'.format(uuid=app_config['uuid'])
		return self._api_post(url, data=data)

	def build(self, config, target):
		'''Start a build on the remote server.

		**NB:** this method blocks until the remote build has completed!

		:return: the primary key of the build
		:raises Exception: if any errors occur during the build
		'''
		LOG.info('Starting new build')
		self._authenticate()

		src_dir = defaults.SRC_DIR

		if not path.isdir(src_dir):
			raise ForgeError("No {0} directory found: are you currently in the right directory?".format(src_dir))

		LOG.info('This could take a while, but will only happen again if you modify config.json')
		build = {
			"state": "pending"
		}
		while build['state'] in ('pending', 'working'):
			build = self._request_development_build(config, target, id=build.get('id', None))

			messages = build.get('messages', None)
			if messages:
				LOG.warning(messages)
				
			if build["state"] == 'complete':
				return build
			
			if not build['state'] in ('pending', 'working'):
				raise ForgeError('build failed: %s' % build['log_output'])
			
			LOG.debug('build {id} is {state}...'.format(id=build['id'], state=build['state']))
			time.sleep(self.POLL_DELAY)

	def server_says_should_rebuild(self, path_to_app="."):
		self._authenticate()
		app_config = build_config.load_app(path_to_app)
		url = 'app/{uuid}/should_rebuild'.format(uuid=app_config['uuid'])
		resp = self._api_get(url,
				params = dict(
					platform_version=app_config['platform_version'],
					platform_changeset=lib.platform_changeset(path_to_app)
				)
		)
		return resp

	def login(self, email, password):
		LOG.info('authenticating as "%s"' % email)
		credentials = {
			'email': email,
			'password': password
		}

		self._api_get('auth/hello')

		self._api_post('auth/verify', data=credentials)
		LOG.info('authentication successful')
		self._authenticated = True

	def logout(self):
		result = self._api_post('auth/logout')
		self.cookies.clear_session_cookies()
		try:
			os.remove(self._path_to_cookies())
		except OSError:
			LOG.debug('Error deleting cookie file', exc_info=True)
		except IOError:
			LOG.debug('Error deleting cookie file', exc_info=True)
		self._authenticated = False
		return result

	def update(self):
		if path.exists(path.join(defaults.FORGE_ROOT, 'no_update')):
			raise ForgeError("Tools tried to update themselves during development")

		write_to_path = path.join(defaults.FORGE_ROOT, 'latest.zip')
		self._get_file(urljoin(self.server, 'latest_tools'), write_to_path)

		above_forge_root = path.normpath(path.join(defaults.FORGE_ROOT, '..'))
		with lib.cd(above_forge_root):
			lib.unzip_with_permissions(write_to_path)

	def signup(self, full_name, email_address, password1, password2):
		"""Create a new user using the signup API
		:param full_name: The full name of the new user
		:type full_name: str

		:param email_address: The email address of the new user
		:type email_address: str

		:param password1: The requested password for the user
		:type password1: str

		:param password2: The password again, for verification purposes
		:type password2: str
		"""
		self._api_get('auth/hello')

		self._api_post('auth/signup', data={
			'name': full_name,
			'email': email_address,
			'password1': password1,
			'password2': password2
		})

		self._authenticated = True

	def available_platforms(self):
		result = self._api_get(
			'available_platforms'
		)

		if result['result'] == 'ok':
			return result['platforms']
		else:
			return {}

	def config_info(self):
		result = self._api_get(
			'config_info'
		)

		if result['result'] == 'ok':
			return result
		else:
			return {}

	def buildevents(self, path_to_app="."):
		self._authenticate()
		app_config = build_config.load_app(path_to_app)
		url = 'reload/buildevents/{uuid}'.format(uuid=app_config['uuid'])
		resp = self._api_get(url)
		return resp

	def create_buildevent(self, app_config):
		self._authenticate()
		result = self._api_post('reload/buildevents/{}'.format(app_config['uuid']),
				files={'config': StringIO(json.dumps(app_config))}
		)
		return result
	
	def normalize_config(self, path_to_app="."):
		self._authenticate()
		app_config = build_config.load_app(path_to_app)
		url = 'reload/{uuid}/normalize_config'.format(uuid=app_config['uuid'])
		resp = self._api_post(url, files={
			'config': StringIO(json.dumps(app_config))
		})
		return resp
	
class FilesUploadDict(object):
	def __init__(self, **files_to_upload):
		try:
			self._files = {}
			for name, location in files_to_upload.items():
				self._files[name] = open(location, mode='rb')
		except IOError as e:
			self._close_files()
			if e.errno == errno.ENOENT:
				raise FormError({name: ['No such file: %s' % location]})
			raise
		except Exception:
			self._close_files()
			raise

	def _close_files(self):
		for name, f in self._files.items():
			try:
				f.close()
			except Exception as e:
				LOG.debug("Failed to close file for %s upload" % name)
				LOG.debug(traceback.format_exc(e))

	def __enter__(self):
		return self._files

	def __exit__(self, *args, **kw):
		self._close_files()
