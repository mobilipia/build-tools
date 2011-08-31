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
from uuid import uuid1
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
		self.app_config_file = 'app-%s.json' % self.config.get('main.uuid')
		
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
		
		if method == "POST":
			# must have CSRF token
			data = kw.get("data", {})
			data["csrfmiddlewaretoken"] = self._csrf_token()
			kw["data"] = data
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
		
	def fetch_unpackaged(self, build_id, to_dir='development'):
		'''Retrieves the unpackaged artefacts for a particular build.
		
		:param build_id: primary key of the build
		:param to_dir: directory that will hold all the unpackged build trees
		'''
		LOG.info('fetching unpackaged artefacts for build %s into "%s"' % (build_id, to_dir))
		self._authenticate()
		
		resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
		content = json.loads(resp.content)
		
		filenames = []
		orig_dir = os.getcwd()
		if not path.isdir(to_dir):
			LOG.warning('creating output directory "%s"' % to_dir)
			os.mkdir(to_dir)
		try:
			os.chdir(to_dir)
			unpackaged = content['unpackaged']
			available_platforms = [plat for plat, url in unpackaged.iteritems() if url]
			for platform in available_platforms:
				filename = urlsplit(unpackaged[platform]).path.split('/')[-1]
				resp = self._get(unpackaged[platform])
				with open(filename, 'w') as out_file:
					LOG.debug('writing %s to %s' % (unpackaged[platform], path.abspath(filename)))
					out_file.write(resp.content)
				# unzip source trees to directories named after platforms
				zipf = zipfile.ZipFile(filename)
				shutil.rmtree(platform, ignore_errors=True)
				LOG.debug('removed "%s" directory' % platform)
				zipf.extractall()
				LOG.debug('extracted unpackaged build for %s' % platform)
				os.remove(filename)
				LOG.debug('removed downloaded file "%s"' % filename)
				filenames.append(path.abspath(platform))
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
		if path.isfile(self.app_config_file):
			with open(self.app_config_file) as app_config:
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
	
	def get_app_config(self, build_id):
		'''Fetch remote App configuration and save to local file
		
		:param build_id: primary key of the build to consider
		:return: the location of the newly-downloaded app configuration
		'''
		LOG.info('fetching remote App configuration for build %s' % build_id)
		self._authenticate()
		resp = self._get(urljoin(self.server, 'build/%d/config/' % build_id))
		config = json.loads(json.loads(resp.content)['config'])
		with open(self.app_config_file, 'w') as out_file:
			out_file.write(json.dumps(config, indent=4))
		LOG.info('wrote App configuration for build %d to "%s"' % (build_id, self.app_config_file))
		return self.app_config_file
		
	def get_latest_user_code(self, to_dir=defaults.USER_DIR):
		'''Fetch the customer's code archive attached to this app
		
		:param to_dir: directory to place the user code into
		:raises Exception: if the :param:`to_dir` already exists
		'''
		LOG.info('fetching customer code')
		if path.exists(to_dir):
			raise Exception('"%s" directory already exists: cannot continue' % to_dir)
		self._authenticate()
		
		resp = self._get(urljoin(self.server, 'app/%s/code/' % self.config.get('main.uuid')))
		code_url = json.loads(resp.content)['code_url']
		LOG.debug('customer code is at %s' % code_url)
		resp = self._get(code_url)
		
		tmp_filename = path.abspath(uuid1().hex)
		with open(tmp_filename, 'w') as tmp_file:
			tmp_file.write(resp.read())
		os.mkdir(to_dir)
		orig_dir = os.getcwd()
		try:
			os.chdir(to_dir)
			tar_file = None
			tar_file = tarfile.open(tmp_filename)
			LOG.info('extracting customer code')
			tar_file.extractall()
		finally:
			os.chdir(orig_dir)
			if tar_file is not None:
				tar_file.close()
			LOG.debug('removing temporary file %s' % tmp_filename)
			os.remove(tmp_filename)