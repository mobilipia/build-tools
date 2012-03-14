'Operations which require involvement of the remote Forge build servers'
from cookielib import LWPCookieJar
import json
import logging
import os
import sys
from os import path
import requests
import shutil
import time
import urlparse
from urlparse import urljoin, urlsplit

import forge
from forge import build, build_config, defaults, ForgeError, lib

LOG = logging.getLogger(__name__)

class RequestError(ForgeError):
	pass

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

	LOG.debug("checking API response for success or error")

	error_template = "Forge API call to {url} went wrong: {reason}"

	if not resp.ok:
		if resp.status_code is None:
			raise RequestError("Request to {url} got no response".format(url=url))
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


def _check_response_for_error(url, method, resp):
	if not resp.ok:
		raise RequestError("Request to {url} went wrong, error code: {code}".format(url=url, code=resp.status_code))

def _cookies_for_domain(domain, cookies):
	return dict((c.name, c.value) for c in cookies if c.domain == domain)

class UpdateRequired(Exception):
	pass

class Remote(object):
	'Wrap remote operations'
	POLL_DELAY = 10

	def __init__(self, config):
		'Start new remote Forge builds'
		self.config = config
		cookie_path = self._path_to_cookies()
		self.cookies = LWPCookieJar(cookie_path)
		if not os.path.exists(cookie_path):
			self.cookies.save()
		else:
			self.cookies.load()
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
		LOG.debug('{method} {url}'.format(method=method.upper(), url=url))
		resp = getattr(requests, method.lower())(url, *args, **kw)

		lib.load_cookies_from_response(resp, self.cookies)
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

	def _get_file_with_progress_bar(self, response, write_to_path, content_length):
		message = 'Fetching ({content_length}) into {out_file}'.format(
			content_length=content_length,
			out_file=write_to_path
		)
		LOG.debug(message)

		progress_bar_width = 50

		progress = 0
		last_mark = 0
		sys.stdout.write("|")

		with open(write_to_path, 'wb') as write_to_file:
			# TODO: upgrade requests, use Response.iter_content
			for chunk in response.iter_content(chunk_size=102400):
				if content_length:
					progress += len(chunk) / content_length
					marks = int(progress * progress_bar_width)

					if marks > last_mark:
						sys.stdout.write("=" * (marks - last_mark))
						last_mark = marks

				write_to_file.write(chunk)
		sys.stdout.write("|\n")

	def _get_file(self, url, write_to_path):
		response = self._get(url)
		try:
			content_length = float(response.headers.get('Content-length'))
		except Exception:
			content_length = None

		if content_length:
			self._get_file_with_progress_bar(response, write_to_path, content_length)
		else:
			with open(write_to_path, 'wb') as write_to_file:
				write_to_file.write(response.content)

	def fetch_initial(self, uuid):
		'''Retrieves the initial project template

		:param uuid: project uuid
		'''
		LOG.info('Fetching initial project template')
		self._authenticate()

		initial_zip_filename = 'initial.zip'

		self._get_file(
			urljoin(self.server, 'app/{uuid}/initial_files/'.format(uuid=uuid)),
			write_to_path=initial_zip_filename
		)
		lib.unzip_with_permissions(initial_zip_filename)
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

	def fetch_unpackaged(self, build_id, to_dir='development'):
		'''Retrieves the unpackaged artefacts for a particular build.
		
		:param build_id: primary key of the build
		:param to_dir: directory that will hold all the unpackged build trees
		'''
		LOG.info('fetching unpackaged artefacts for build %s into "%s"' % (build_id, to_dir))
		self._authenticate()
		
		output_key = 'unpackaged'
		build = self._api_get('build/{id}/detail/'.format(id=build_id))
		
		if 'log_output' in build:
			# too chatty, and already seen this after build completed
			del build['log_output']
		LOG.debug('build detail: %s' % build)
		
		filenames = []
		if not path.isdir(to_dir):
			LOG.info('creating output directory "%s"' % to_dir)
			os.mkdir(to_dir)
			
		with lib.cd(to_dir):
			locations = build[output_key]
			available_platforms = [plat for plat, url in locations.iteritems() if url]
			
			for platform in available_platforms:
				filename = urlsplit(locations[platform]).path.split('/')[-1]
				
				LOG.debug('writing %s to %s' % (locations[platform], path.abspath(filename)))
				self._get_file(
					locations[platform],
					write_to_path=filename
				)
				
				self._handle_unpackaged(platform, filename)
				
				filenames.append(path.abspath(platform))
		
		LOG.info('fetched build into "%s"' % '", "'.join(filenames))
		return filenames

	def fetch_generate_instructions(self, build_id, to_dir):
		'''Retreive the generation instructions for a particular build.

		Rather than hard-coding these instructions - how to inject customer
		code into the apps - they are loaded dynamically from the server to
		allow for different platforms versions to work with a larger number
		of build-tools versions.

		:param build_id: primary key of the build to get instructions for
		:param to_dir: where the instructions will be put
		'''
		LOG.info("fetching generation instructions for build {build_id} into {to_dir}".format(**locals()))

		self._authenticate()

		temp_instructions_file = 'instructions.zip'

		try:
			# ensure generate_dynamic dir is there before extracting instructions into it
			if not path.isdir(to_dir):
				os.makedirs(to_dir)

			with lib.cd(to_dir):
				self._get_file(
					urljoin(self.server, 'build/{build_id}/generate_instructions/'.format(build_id=build_id)),
					temp_instructions_file
				)
				lib.unzip_with_permissions(temp_instructions_file)

		finally:
			if path.isfile(path.join(to_dir, temp_instructions_file)):
				os.remove(path.join(to_dir, temp_instructions_file))

		return to_dir

	def _request_development_build(self):
		data = {}
		app_config = build_config.load_app()
		data['config'] = json.dumps(app_config)
		
		url = 'app/{uuid}/template'.format(uuid=app_config['uuid'])
		return self._api_post(url, data=data)

	def _poll_until_build_complete(self, build_id):
		build = self._api_get('build/{id}/detail/'.format(id=build_id))

		while build['state'] in ('pending', 'working'):
			LOG.debug('build {id} is {state}...'.format(id=build_id, state=build['state']))
			time.sleep(self.POLL_DELAY)
			build = self._api_get('build/{id}/detail/'.format(id=build_id))

		if build['state'] in ('complete',):
			LOG.info('build completed successfully')
			LOG.debug(build['log_output'])
			return

		else:
			raise ForgeError('build failed: %s' % build['log_output'])

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
		LOG.info('Starting new build')
		self._authenticate()

		src_dir = defaults.SRC_DIR

		if not path.isdir(src_dir):
			raise ForgeError("No {0} directory found: are you currently in the right directory?".format(src_dir))

		resp = self._request_development_build()

		build_id = resp['build_id']
		messages = resp.get('build_messages', None)
		if messages:
			LOG.warning(messages)
		LOG.info('Build %s started...' % build_id)

		LOG.info('This could take a while, but will only happen again if you modify config.json')
		self._poll_until_build_complete(build_id)
		return build_id

	def server_says_should_rebuild(self):
		app_config = build_config.load_app()
		url = 'app/{uuid}/should_rebuild'.format(uuid=app_config['uuid'])
		resp = self._api_get(url,
				params = dict(
					platform_version=app_config['platform_version'],
					platform_changeset=lib.platform_changeset(),
					targets=",".join(build._enabled_platforms('development')),
				)
		)
		return resp["should_rebuild"], resp["reason"]

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
		write_to_path = path.join(defaults.FORGE_ROOT, 'latest.zip')
		self._get_file(urljoin(self.server, 'latest_tools'), write_to_path)

		above_forge_root = path.normpath(path.join(defaults.FORGE_ROOT, '..'))
		with lib.cd(above_forge_root):
			lib.unzip_with_permissions(write_to_path)
