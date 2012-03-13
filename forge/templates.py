'''To enable quick, local-only builds, we create generic templated builds
to start with, and inject the user code into those templates whenever possible.
'''
import codecs
from datetime import datetime
import hashlib
import logging
from os import path
import shutil
import subprocess
import sys

from forge import defaults
from forge.build import create_build, import_generate_dynamic
from forge.remote import Remote

LOG = logging.getLogger(__name__)

class Manager(object):
	'Handles the fetching, updating and management of generic templates'
	
	
	def __init__(self, config, tmpl_dir=None):
		'''Operations on the locally stored template code
		
		:param config: build configuration object
		:type config: ``dict``
		:param tmpl_dir: directory name in which the templates will be sat
		'''
		if tmpl_dir is None:
			self._tmpl_dir = defaults.TEMPLATE_DIR
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
		
	def templates_for_config(self):
		'''Determine whether we have current templates for the user's configuration.
		
		:rtype: bool
		'''
		if not path.isdir(self._tmpl_dir):
			LOG.info("{tmpl} is not a directory: don't have templates yet".format(tmpl=self._tmpl_dir))
			return False
		old_config_file = path.join(self._tmpl_dir, "config.json")
		if not path.isfile(old_config_file):
			LOG.info("{file} does not exist: we need to fetch new templates".format(file=old_config_file))
			return False
		
		generate_dynamic = import_generate_dynamic()
		return generate_dynamic.internal_goals.config_changes_invalidate_templates(
				generate_module=generate_dynamic,
				old_config_file=old_config_file,
				new_config_file=defaults.APP_CONFIG_FILE,
		)
		
	def fetch_templates(self, build_id, clean=False):
		'''Retrieve remote template files for a specified build, and the config to match.
		
		:param build_id: the primary key of the build
		:param clean: should we remove any existing templates first?
		'''
		remote = Remote(self._config)

		template_dir = self.templates_for_config()
		if template_dir and not clean:
			LOG.info('already have templates for current App configuration')
			return template_dir

		config_hash = self._hash_file(defaults.APP_CONFIG_FILE)
		LOG.info('current configuration hash is %s' % config_hash)
		
		# remove old templates
		LOG.debug('removing %s' % self._tmpl_dir)
		shutil.rmtree(self._tmpl_dir, ignore_errors=True)
		
		# grab templated platform
		LOG.info('fetching new Forge templates')
		remote.fetch_unpackaged(build_id, to_dir=self._tmpl_dir)
		if sys.platform == 'win32':
			try:
				subprocess.call(['attrib', '+h', self._tmpl_dir])
			except:
				# don't care if we fail to set the templates dir as hidden
				pass
		
		with open(path.join(self._tmpl_dir, config_hash+'.hash'), 'w') as marker:
			marker.write(str(datetime.utcnow()))
		
		return self._tmpl_dir
