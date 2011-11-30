'Operations which require involvement of the remote WebMynd build servers'
from cookielib import LWPCookieJar
from getpass import getpass
import json
import logging
import os
from os import path
import requests
import shutil
import subprocess
import tarfile
import time
from urlparse import urljoin, urlsplit
import zipfile

import webmynd
from webmynd import ForgeError
from webmynd import defaults
from webmynd import lib

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
		'''Expects ``__method`` entry in :param:`**kw`
		'''
		method = kw['__method']
		del kw['__method']
		
		if method == "POST":
			# must have CSRF token
			data = kw.get("data", {})
			data['build_tools_version'] = webmynd.get_version()
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

		if 'username' in webmynd.settings:
			email = webmynd.settings['username']
		else:
			email = raw_input("Your email address: ")

		if 'password' in webmynd.settings:
			password = webmynd.settings['password']
		else:
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
		return self._api_post('app/', data=data)['uuid']

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

				post_get_fn(platform, filename)

				filenames.append(path.abspath(platform))
			return filenames

	def check_version(self):
		result = self._api_get(
			'version_check/{version}/'.format(version=webmynd.get_version().replace('.','/'))
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

	def _get_file(self, url, write_to_path):
		response = self._get(url)
		content_length = response.headers.get('Content-length')

		if content_length:
			message = 'Fetching ({content_length}) into {out_file}'.format(
				content_length=content_length,
				out_file=write_to_path
			)
			LOG.debug(message)

		with open(write_to_path, 'wb') as write_to_file:
			# TODO: upgrade requests, use Response.iter_content
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

		# XXX: shouldn't do the renaming here
		# need to fix the server to serve up the correct structure
		shutil.move('user', defaults.SRC_DIR)

		os.remove(initial_zip_filename)
		LOG.debug('Removed downloaded file "%s"' % initial_zip_filename)

	def _handle_packaged(self, platform, filename):
		'No-op'
		pass

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

		filenames = self._fetch_output(build_id, to_dir, 'unpackaged', self._handle_unpackaged)
			
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
			# ensure generate_dynamic dir is empty before extracting instructions into it
			if path.isdir(to_dir):
				shutil.rmtree(to_dir, ignore_errors=True)
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

	def _request_build(self, development, template_only, data=None, files=None):
		if data is None:
			data = {}

		# TODO can we just use self.config here?
		if path.isfile(defaults.APP_CONFIG_FILE):
			with lib.open_file(defaults.APP_CONFIG_FILE) as app_config:
				data['config'] = app_config.read()

		url = 'app/%s/%s/%s' % (
			self.config.get('uuid'),
			'template' if template_only else 'build',
			'development' if development else ''
		)
		return self._api_post(url, data=data, files=files)

	def _request_development_build(self):
		return self._request_build(
			development=True,
			template_only=True,
		)

	def _create_src_tar(self, archive_filename, directory_to_archive):
		# TODO skip over files specified by some .forgeignore file
		src_archive = tarfile.open(archive_filename, mode='w:bz2')

		with lib.cd(directory_to_archive):
			for user_file in os.listdir('.'):
				src_archive.add(user_file)
				LOG.debug('added "%s" to user archive' % user_file)

		src_archive.close()
		return src_archive

	def _request_production_build(self):
		src_dir = defaults.SRC_DIR
		src_archive_filename = 'user.%s.tar.bz2' % time.time()

		try:
			src_archive = None
			src_archive = self._create_src_tar(src_archive_filename, src_dir)

			with lib.open_file(src_archive_filename, mode='rb') as user_files:
				LOG.info('Uploading application source code ({size})...'.format(
					size=lib.human_readable_file_size(user_files)
				))

				return self._request_build(
					development=False,
					template_only=False,
					files={'user.tar.bz2': user_files}
				)
		finally:
			try:
				os.remove(src_archive_filename)
			except OSError:
				# wasn't created
				pass

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

		if template_only:
			resp = self._request_development_build()
		else:
			resp = self._request_production_build()

		build_id = resp['build_id']
		LOG.info('Build %s started...' % build_id)

		if development:
			LOG.info('This could take a while, but will only happen again if you modify config.json')
		else:
			LOG.info('This could take a while, any production build requires a full build with the Forge service')

		self._poll_until_build_complete(build_id)
		return build_id