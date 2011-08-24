'Operations which require involvement of the remote WebMynd build servers'
from cookielib import CookieJar
import json
import logging
import os
from os import path
import shutil
import tarfile
import time
from urlparse import urljoin, urlsplit
import zipfile

import requests

from webmynd import defaults

LOG = logging.getLogger(__name__)

class Remote(object):
	'Wrap remote operations'
	POLL_DELAY = 10
	
	def __init__(self, config):
		'Start new remote WebMynd builds'
		self.config = config
		self.cookies = CookieJar()
		self._authenticated = False
		
	@property
	def server(self):
		'The URL of the build server to use (default http://www.webmynd.com/api/)'
		return self.config.get('main.server', default='http://www.webmynd.com/api/')
	def _csrf_token(self):
		'''Return the server-negotiated CSRF token, if we have one
		
		:raises Exception: if we don't have a CSRF token
		'''
		for cookie in self.cookies:
			if cookie.name == 'csrftoken':
				return cookie.value
		else:
			raise Exception("We don't have a CSRF token")
		
	def __get_or_post(self, *args, **kw):
		'''Expects ``__method`` and ``__error_message`` entries in :param:`**kw`
		'''
		method = kw['__method']
		del kw['__method']
		if '__error_message' in kw:
			error_message = kw['__error_message']
			del kw['__error_message']
		else:
			error_message = method+' to %(url)s failed: status code %(status_code)s\n%(content)s'
			
		data = kw.get('data', {})
		if method == 'POST':
			data['csrfmiddlewaretoken'] = self._csrf_token()
		kw['data'] = data
		kw['cookies'] = self.cookies
		resp = getattr(requests, method.lower())(*args, **kw)
		if not resp.ok:
			try:
				msg = error_message % resp.__dict__
			except KeyError: # in case error_message is looking for something resp doesn't have
				msg = method+' to %s failed %s: %s' % (
					getattr(resp, 'url', 'unknown URL'),
					str(resp),
					getattr(resp, 'content', 'unknown error')
				)
			raise Exception(msg)
		return resp
	def _post(self, *args, **kw):
		'''Make a POST request.
		
		:param:`*args` and :param:`**kw` are passed through to the
		:module:`requests` library.
		'''
		kw['__method'] = 'POST'
		return self.__get_or_post(*args, **kw)

	def _get(self, *args, **kw):
		'''Make a GET request.
		
		:param:`*args` and :param:`**kw` are passed through to the
		:module:`requests` library.
		'''
		kw['__method'] = 'GET'
		return self.__get_or_post(*args, **kw)
		
	def _authenticate(self):
		'''Authentication handshake with server (if we haven't already')
		'''
		if self._authenticated:
			LOG.debug('already authenticated - continuing')
			return
		LOG.info('authenticating as "%s"' % self.config.get('authentication.username'))
		credentials = {
			'username': self.config.get('authentication.username'),
			'password': self.config.get('authentication.password')
		}
		if credentials['password'] == defaults.PASSWORD:
			msg = 'have you updated your password in %s?' % self.config.build_config_file
			LOG.error(msg)
			raise Exception(msg)
		self._get(urljoin(self.server, 'auth/hello'))
			
		self._post(urljoin(self.server, 'auth/verify'), data=credentials)
		LOG.info('authentication successful')
		self._authenticated = True
		
	def latest(self):
		'''Get the ID of the latest completed production build for this app.'''
		LOG.info('fetching latest build ID')
		self._authenticate()
		
		resp = self._get(urljoin(self.server, 'app/%s/latest/' % self.config.get('main.uuid')))
		return json.loads(resp.content)['build_id']

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
		resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
		content = json.loads(resp.content)
		
		filenames = []
		if not path.isdir(to_dir):
			LOG.warning('creating output directory "%s"' % to_dir)
			os.mkdir(to_dir)
		os.chdir(to_dir)
		locations = content[output_key]
		available_platforms = [plat for plat, url in locations.iteritems() if url]
		for platform in available_platforms:
			filename = urlsplit(locations[platform]).path.split('/')[-1]
			resp = self._get(locations[platform])
			with open(filename, 'w') as out_file:
				LOG.debug('writing %s to %s' % (locations[platform], path.abspath(filename)))
				out_file.write(resp.content)
			post_get_fn(platform, filename)
			filenames.append(path.abspath(platform))
		return filenames
			
	def _handle_packaged(self, platform, filename):
		'No-op'
		pass

	def _handle_unpackaged(self, platform, filename):
		'''De-compress a built output tree.
		
		:param platform: e.g. "chrome", "ios" - we expect the contents of the ZIP file to
			contain a directory named after the relevant platform
		:param filename: the ZIP file to extract
		'''
		zipf = zipfile.ZipFile(filename)
		shutil.rmtree(platform, ignore_errors=True)
		LOG.debug('removed "%s" directory' % platform)
		zipf.extractall()
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
		if path.isfile(self.config.app_config_file):
			with open(self.config.app_config_file) as app_config:
				data['config'] = app_config.read()
		def build_request(files=None):
			'build the URL to start a build, then POST it'
			url_path = 'app/%s/%s/%s' % (
				self.config.get('main.uuid'),
				'template' if template_only else 'build',
				'development' if development else ''
			)
			url = urljoin(self.server, url_path)
			return self._post(url, data=data, files=files)
			
		user_dir = defaults.USER_DIR
		if template_only or not path.isdir(user_dir):
			if not path.isdir(user_dir):
				LOG.warning('no "user" directory found - we will be using the App\'s default code!')
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
		
				with open(filename, mode='r') as user_files:
					resp = build_request({'user.tar.bz2': user_files})
			finally:
				try:
					os.remove(filename)
				except OSError:
					# wasn't created
					pass
					
		build_id = json.loads(resp.content)['build_id']
		LOG.info('build %s started...' % build_id)
		
		resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
		content = json.loads(resp.content)
		while content['state'] in ('pending', 'working'):
			LOG.debug('build %s is %s...' % (build_id, content['state']))
			time.sleep(self.POLL_DELAY)
			resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
			content = json.loads(resp.content)
			
		if content['state'] in ('complete',):
			LOG.info('build completed successfully')
			LOG.debug(content['log_output'])
			return build_id
		else:
			raise Exception('build failed: %s' % content['log_output'])