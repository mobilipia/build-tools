'''To enable quick, local-only builds, we create generic templated builds
to start with, and inject the user code into those templates whenever possible.
'''
import logging
from os import path
import shutil
import subprocess
import sys

from forge import defaults
from forge.build import import_generate_dynamic
from forge.remote import Remote

LOG = logging.getLogger(__name__)

class Manager(object):
	'Handles the fetching, updating and management of generic templates'
	
	
	def __init__(self, config):
		'''Operations on the locally stored template code
		
		:param config: build configuration object
		:type config: ``dict``
		:param tmpl_dir: directory name in which the templates will be sat
		'''
		self._tmpl_dir = defaults.TEMPLATE_DIR
		self._config = config
		
	def need_new_templates_for_config(self):
		'''Determine whether we have current templates for the user's configuration.
		
		:rtype: bool
		'''
		if not path.isdir(self._tmpl_dir):
			LOG.debug("{tmpl} is not a directory: don't have templates".format(tmpl=self._tmpl_dir))
			return True
		old_config_filename = path.join(self._tmpl_dir, "config.json")
		if not path.isfile(old_config_filename):
			LOG.debug("{file} does not exist: we need to fetch new templates".format(
				file=old_config_filename))
			return True
		
		generate_dynamic = import_generate_dynamic()
		return generate_dynamic.internal_goals.config_changes_invalidate_templates(
				generate=generate_dynamic,
				old_config_filename=old_config_filename,
				new_config_filename=defaults.APP_CONFIG_FILE,
		)
		
	def fetch_templates(self, build):
		'''
		Retrieve remote template files for a specified build, and the config to match.
		
		:param build: the build to fetch templates for
		'''
		remote = Remote(self._config)
		
		# remove old templates
		LOG.debug('removing %s' % self._tmpl_dir)
		shutil.rmtree(self._tmpl_dir, ignore_errors=True)
		
		# grab templated platform
		LOG.info('fetching new Forge templates')
		remote.fetch_unpackaged(build, to_dir=self._tmpl_dir)
		if sys.platform == 'win32':
			try:
				subprocess.call(['attrib', '+h', self._tmpl_dir])
			except Exception:
				# don't care if we fail to hide the templates dir
				pass

		# copy config.json across to be compared to next time
		shutil.copy(
				defaults.APP_CONFIG_FILE,
				path.join(self._tmpl_dir, "config.json"))
		
		return self._tmpl_dir
