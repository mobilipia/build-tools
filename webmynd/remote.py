'Operations which require involvement of the remote WebMynd build servers'
from cookielib import LWPCookieJar
import json
import logging
import os
from os import path
import shutil
import tarfile
import time
from urlparse import urljoin, urlsplit
import zipfile
from getpass import getpass
import requests
import subprocess

import webmynd
from webmynd import ForgeError
from webmynd import defaults

LOG = logging.getLogger(__name__)

class RequestError(ForgeError):
	pass

def _check_api_response_for_error(url, method, resp, error_message=None):
	'''Check an API response from the website to see if there was an error. Checks for one of the following:

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

	LOG.debug("checking API response for success or error")

	error_template = "Forge API call to {url} went wrong: {reason}"

	if not resp.ok:
		try:
			content_dict = json.loads(resp.content)
			if content_dict['result'] == 'error':
				reason = content_dict.get('text', 'Unknown error')
				error_message = error_template.format(url=url, reason=reason)
				raise RequestError(error_message)

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
			raise RequestError(msg)
	else:
		try:
			content_dict = json.loads(resp.content)
			if content_dict['result'] == 'error':
				reason = content_dict.get('text', 'unknown error')
				error_message = error_template.format(reason=reason, url=url)
				raise RequestError(error_message)

		except ValueError:
			reason = 'Server meant to respond with JSON, but response content was: %s' % resp.content
			error_message = error_template.format(reason=reason, url=url)
			raise RequestError(reason)

class Remote(object):
	'Wrap remote operations'
	POLL_DELAY = 10

	def __init__(self, config):
		'Start new remote WebMynd builds'
		self.config = config
		cookie_path = path.join(defaults.FORGE_ROOT, 'cookies.txt')
		self.cookies = LWPCookieJar(cookie_path)
		if not os.path.exists(cookie_path):
			self.cookies.save()
		else:
			self.cookies.load()
		self._authenticated = False

	@property
	def server(self):
		'The URL of the build server to use (default http://www.webmynd.com/api/)'
		return self.config.get('main', {}).get('server', 'http://www.webmynd.com/api/')

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
		'''Expects ``__method`` and ``__error_message`` entries in :param:`**kw`
		'''
		method = kw['__method']
		del kw['__method']
		if '__error_message' in kw:
			error_message = kw['__error_message']
			del kw['__error_message']
		else:
			error_message = method+' to %(url)s failed: status code %(status_code)s\n%(content)s'

		if method == "POST":
			# must have CSRF token
			data = kw.get("data", {})
			data["csrfmiddlewaretoken"] = self._csrf_token()
			kw["data"] = data
		kw['cookies'] = self.cookies
		kw['headers'] = {'REFERER': url}

		if self.config.get('main', {}).get('authentication'):
			kw['auth'] = (
				self.config['main']['authentication'].get('username'),
				self.config['main']['authentication'].get('password')
			)
		LOG.debug('{method} {url}'.format(method=method.upper(), url=url))
		resp = getattr(requests, method.lower())(url, *args, **kw)

		self.cookies.save()
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
		return self.__get_or_post(url, *args, **kw)

	def _post(self, url, *args, **kw):
		'''Make a GET request.
		
		:param url: see :module:`requests`
		:param *args: see :module:`requests`
		'''
		kw['__method'] = 'POST'
		return self.__get_or_post(url, *args, **kw)

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

		email = raw_input("Your email address: ")
		password = getpass()
		LOG.info('authenticating as "%s"' % email)
		credentials = {
			'email': email,
			'password': password
		}

		self._api_get('auth/hello')
		
		self._api_post('auth/verify', data=credentials)
		LOG.info('authentication successful')
		self._authenticated = True

	def create(self, name):
		self._authenticate()
	
		data = {
			'name': name
		}
		resp = self._api_post('app/', data=data)
		return json.loads(resp.content)['uuid']

	def latest(self):
		'''Get the ID of the latest completed production build for this app.'''
		LOG.info('fetching latest build ID')
		self._authenticate()
		
		return self._api_get('app/{uuid}/latest/'.format(uuid=self.config.get('uuid')))

	def _fetch_output(self, build_id, to_dir, output_key, post_get_fn):
		'''Helper function for common file-getting logic of the fetch* methods.
		
		:param build_id: primary key of the build
		:param to_dir: directory name to fetch the files into
		:param output_key: which section of the build detail to look inside
			(normally "unpackaged" or "packaged")
		:param post_get_fn: function to invoke with two parameters: the name of the current
			platform and the name of the downloaded file. Will be invoked in the same directory
			as the file was downloaded to.
		'''
		build = self._api_get('build/{id}/detail/'.format(id=build_id))
		if 'log_output' in build:
			# too chatty, and already seen this after build completed
			del build['log_output']
		LOG.debug('build detail: %s' % build)
		
		filenames = []
		if not path.isdir(to_dir):
			LOG.warning('creating output directory "%s"' % to_dir)
			os.mkdir(to_dir)

		os.chdir(to_dir)
		locations = build[output_key]
		available_platforms = [plat for plat, url in locations.iteritems() if url]

		for platform in available_platforms:
			filename = urlsplit(locations[platform]).path.split('/')[-1]

			resp = self._get(locations[platform])

			with open(filename, 'wb') as out_file:
				LOG.debug('writing %s to %s' % (locations[platform], path.abspath(filename)))
				out_file.write(resp.content)

			post_get_fn(platform, filename)

			filenames.append(path.abspath(platform))
		return filenames

	def check_version(self):
		result = self._api_get(
			'version_check/{version}/'.format(version=webmynd.VERSION.replace('.','/'))
		)

		if result['result'] == 'ok':
			if 'upgrade' in result:
				LOG.info('Update result: %s' % result['message'])
			else:
				LOG.debug('Update result: %s' % result['message'])
			
			if result.get('upgrade') == 'required':
				raise ForgeError("""An update to these command line tools is required

The newest tools can be obtained from https://webmynd.com/forge/upgrade/
""")
		else:
			LOG.info('Upgrade check failed.')
		
	def fetch_initial(self, uuid):
		'''Retrieves the initial project template
		
		:param uuid: project uuid
		'''
		LOG.info('fetching initial project template')
		self._authenticate()
		
		resp = self._get('app/{uuid}/initial_files'.format(uuid=uuid))

		filename = 'initial.zip'
		with open(filename, 'wb') as out_file:
			LOG.debug('writing %s' % path.abspath(filename))
			out_file.write(resp.content)

		zipf = zipfile.ZipFile(filename)
		# XXX: shouldn't do the renaming here - need to fix the server to serve up the correct structure
		zipf.extractall()
		shutil.move('user', defaults.SRC_DIR)
		zipf.close()
		LOG.debug('extracted initial project template')
		os.remove(filename)
		LOG.debug('removed downloaded file "%s"' % filename)
		
	def _handle_packaged(self, platform, filename):
		'No-op'
		pass

	@staticmethod
	def _unzip_with_permissions(filename):
		try:
			subprocess.Popen(["unzip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		except OSError:
			LOG.debug("'unzip' not available, falling back on python ZipFile, this will strip certain permissions from files")
			zip_to_extract = zipfile.ZipFile(filename)
			zip_to_extract.extractall()
			zip_to_extract.close()
		else:
			LOG.debug("unzip is available, using it")
			zip_process = subprocess.Popen(["unzip", filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			output = zip_process.communicate()[0]
			LOG.debug("unzip output")
			LOG.debug(output)

	def _handle_unpackaged(self, platform, filename):
		'''De-compress a built output tree.
		
		:param platform: e.g. "chrome", "ios" - we expect the contents of the ZIP file to
			contain a directory named after the relevant platform
		:param filename: the ZIP file to extract
		'''
		shutil.rmtree(platform, ignore_errors=True)
		LOG.debug('removed "%s" directory' % platform)

		self._unzip_with_permissions(filename)
		LOG.debug('extracted unpackaged build for %s' % platform)

		os.remove(filename)
		LOG.debug('removed downloaded file "%s"' % filename)

	def fetch_packaged(self, build_id, to_dir='production'):
		'''Retrieves the packaged artefacts for a particular build.
		
		:param build_id: primary key of the build
		:param to_dir: directory that will hold the packaged output
		'''
		LOG.info('fetching packaged artefacts for build %s into "%s"' % (build_id, to_dir))
		self._authenticate()

		orig_dir = os.getcwd()
		try:
			filenames = self._fetch_output(build_id, to_dir, 'packaged', self._handle_packaged)
		finally:
			os.chdir(orig_dir)

		LOG.info('fetched build into "%s"' % '", "'.join(filenames))
		return filenames
		
	def fetch_unpackaged(self, build_id, to_dir='development'):
		'''Retrieves the unpackaged artefacts for a particular build.
		
		:param build_id: primary key of the build
		:param to_dir: directory that will hold all the unpackged build trees
		'''
		LOG.info('fetching unpackaged artefacts for build %s into "%s"' % (build_id, to_dir))
		self._authenticate()

		orig_dir = os.getcwd()
		try:
			filenames = self._fetch_output(build_id, to_dir, 'unpackaged', self._handle_unpackaged)
		finally:
			os.chdir(orig_dir)
			
		LOG.info('fetched build into "%s"' % '", "'.join(filenames))
		return filenames
	
	def build(self, development=True, template_only=False):
		'''Start a build on the remote server.
		
		**NB:** this method blocks until the remote build has completed!
		
		:param development: if ``True``, we will not do any packaging of the
			build; it will be left in an expanded directory layout
		:param template_only: internal use only: if ``True`` we will not use
			the "user" code - we will just recreate the app templates using the
			current app configuration
		:return: the primary key of the build
		:raises Exception: if any errors occur during the build
		'''
		LOG.info('starting new build')
		self._authenticate()
		
		data = {}

		if path.isfile(defaults.APP_CONFIG_FILE):
			with open(defaults.APP_CONFIG_FILE) as app_config:
				data['config'] = app_config.read()
				pass

		def build_request(files=None):
			'build the URL to start a build, then POST it'
			url = 'app/%s/%s/%s' % (
				self.config.get('uuid'),
				'template' if template_only else 'build',
				'development' if development else ''
			)
			return self._api_post(url, data=data, files=files)
			
		user_dir = defaults.SRC_DIR
		if template_only or not path.isdir(user_dir):
			if not path.isdir(user_dir):
				LOG.warning('no "%s" directory found - we will be using the App\'s default code!' % defaults.SRC_DIR)
			resp = build_request()
		else:
			filename, orig_dir = 'user.%s.tar.bz2' % time.time(), os.getcwd()
			try:
				user_comp = None
				user_comp = tarfile.open(filename, mode='w:bz2')
				os.chdir(user_dir)
				for user_file in os.listdir('.'):
					user_comp.add(user_file)
					LOG.debug('added "%s" to user archive' % user_file)
				os.chdir(orig_dir)
				user_comp.close()
		
				with open(filename, mode='rb') as user_files:
					resp = build_request({'user.tar.bz2': user_files})
			finally:
				try:
					os.remove(filename)
				except OSError:
					# wasn't created
					pass
					
		build_id = resp['build_id']
		LOG.info('build %s started...' % build_id)
		
		build = self._api_get('build/{id}/detail/'.format(id=build_id))

		while build['state'] in ('pending', 'working'):
			LOG.debug('build {id} is {state}...'.format(id=build_id, state=build['state']))
			time.sleep(self.POLL_DELAY)
			build = self._api_get('build/{id}/detail'.format(id=build_id))

		if build['state'] in ('complete',):
			LOG.info('build completed successfully')
			LOG.debug(build['log_output'])
			return build_id

		else:
			raise Exception('build failed: %s' % build['log_output'])
