import codecs
from datetime import datetime
import hashlib
import logging
import os
from os import path
import shutil

from remote import Remote

log = logging.getLogger(__name__)

class Manager(object):
	__DEFAULT_TMPL_DIR = '.template'
	
	def __init__(self, config, tmpl_dir=None):
		'''Operations on the locally stored template code
		
		:param config: build configuration object
		:type config: :class:`webmynd.config.BuildConfig`
		:param tmpl_dir: directory name in which the templates will be sat
		'''
		if tmpl_dir is None:
			self._tmpl_dir = self.__DEFAULT_TMPL_DIR
		else:
			self._tmpl_dir = tmpl_dir
		self._config = config
		
	def _hash_file(self, config_filename):
		hsh = hashlib.md5()
		
		with codecs.open(config_filename) as config_file:
			hsh.update(config_file.read())
		
		return hsh.hexdigest()
		
	def templates_for(self, config_filename):
		'''Determine template files directory for the given configuration.
		
		:param config_filename: name of configuration file to consider
		:return: the relevant templates directory if it exists, or ``None``
		'''
		config_hash = self._hash_file(config_filename)
		if path.exists(path.join(self._tmpl_dir, config_hash+'.hash')):
			return self._tmpl_dir
		else:
			return None
		
	def get_templates(self, build_id):
		'''Retrieve remote template files for a specified build, and the config to match.
		
		:param build_id: the primary key of the build
		'''
		remote = Remote(self._config)

		config_filename = remote.get_app_config(build_id)
		template_dir = self.templates_for(config_filename)
		if template_dir:
			log.info('already have templates for current App configuration')
			return template_dir

		config_hash = self._hash_file(config_filename)
		log.info('current configuration hash is %s' % config_hash)
		
		# remove old templates
		log.debug('removing %s' % self._tmpl_dir)
		shutil.rmtree(self._tmpl_dir, ignore_errors=True)
		
		# grab templated platform
		log.info('fetching new WebMynd templates')
		remote.fetch_unpackaged(build_id, to_dir=self._tmpl_dir)
		
		with open(path.join(self._tmpl_dir, config_hash+'.hash'), 'w') as marker:
			marker.write(str(datetime.utcnow()))
		
		return self._tmpl_dir