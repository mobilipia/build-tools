'''To enable quick, local-only builds, we create generic templated builds
to start with, and inject the user code into those templates whenever possible.
'''
import codecs
from datetime import datetime
import hashlib
import logging
from os import path
import shutil

from webmynd import defaults
from webmynd.remote import Remote

LOG = logging.getLogger(__name__)

class Manager(object):
	'Handles the fetching, updating and management of generic templates'
	__DEFAULT_TMPL_DIR = '.template'
	
	def __init__(self, config, tmpl_dir=None):
		'''Operations on the locally stored template code
		
		:param config: build configuration object
		:type config: ``dict``
		:param tmpl_dir: directory name in which the templates will be sat
		'''
		if tmpl_dir is None:
			self._tmpl_dir = self.__DEFAULT_TMPL_DIR
		else:
			self._tmpl_dir = tmpl_dir
		self._config = config
		
	def _hash_file(self, config_filename):
		'''Compute the hash of a file.
		
		:param config_filename: the name of a file to read and hash
		:return: string version of the hash
		'''
		hsh = hashlib.md5()
		
		with codecs.open(config_filename) as config_file:
			hsh.update(config_file.read())
		
		return hsh.hexdigest()
		
	def templates_for_config(self, config_filename):
		'''Determine template files directory for the given configuration.
		
		:param config_filename: name of configuration file to consider
		:return: the relevant templates directory if it exists, or ``None``
		'''
		config_hash = self._hash_file(config_filename)
		if path.exists(path.join(self._tmpl_dir, config_hash+'.hash')):
			return self._tmpl_dir
		else:
			return None
		
	def fetch_templates(self, build_id):
		'''Retrieve remote template files for a specified build, and the config to match.
		
		:param build_id: the primary key of the build
		'''
		remote = Remote(self._config)

		template_dir = self.templates_for_config(defaults.APP_CONFIG_FILE)
		if template_dir:
			LOG.info('already have templates for current App configuration')
			return template_dir

		config_hash = self._hash_file(defaults.APP_CONFIG_FILE)
		LOG.info('current configuration hash is %s' % config_hash)
		
		# remove old templates
		LOG.debug('removing %s' % self._tmpl_dir)
		shutil.rmtree(self._tmpl_dir, ignore_errors=True)
		
		# grab templated platform
		LOG.info('fetching new WebMynd templates')
		remote.fetch_unpackaged(build_id, to_dir=self._tmpl_dir)
		
		with open(path.join(self._tmpl_dir, config_hash+'.hash'), 'w') as marker:
			marker.write(str(datetime.utcnow()))
		
		return self._tmpl_dir