'''To enable quick, local-only builds, we create generic templated builds
to start with, and inject the user code into those templates whenever possible.
'''
import logging
from os import path
import shutil
import tempfile

from forge import defaults
from forge import lib
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
		self._instructions_dir = defaults.INSTRUCTIONS_DIR
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
		
	def fetch_template_apps_and_instructions(self, build):
		'''Retrieve everything needed for the customer side of the build process,
		and replace the current templates/instructions.

		* Template apps for each platform
		* generate_dynamic python module
		* various helper programs/schema files into a lib folder
		
		:param build: the build id to fetch templates for

		*N.B.* Assumes working directory is the app dir
		'''
		remote = Remote(self._config)

		temp_dir = None
		try:
			temp_dir = tempfile.mkdtemp(prefix="forge-templates-")
			temp_templates_dir = path.join(temp_dir, self._tmpl_dir)
			temp_instructions_dir = path.join(temp_dir, self._instructions_dir)
			final_templates_dir = self._tmpl_dir

			remote.fetch_unpackaged(build, to_dir=temp_templates_dir)
			remote.fetch_generate_instructions(temp_instructions_dir)

			lib.set_file_as_hidden(final_templates_dir)

			# copy config.json across to be compared to next time
			shutil.copy(
					defaults.APP_CONFIG_FILE,
					path.join(temp_templates_dir, "config.json"))

			# XXX: assumption here that instructions dir is inside of
			# the templates dir (currently it is the same)
			# remove old templates
			LOG.info('Removing old templates if present')
			LOG.debug('Removing %s ' % final_templates_dir)
			shutil.rmtree(final_templates_dir, ignore_errors=True)

			LOG.info('Using new templates')
			LOG.debug('Moving %s to %s' % (temp_templates_dir, final_templates_dir))
			shutil.move(temp_templates_dir, final_templates_dir)

			# invalidate any caching of previous generate_dynamic module after
			# fetching templates
			# XXX: might make more sense to just force do_reload=True on every import and
			# get rid of this?
			import_generate_dynamic(do_reload=True)
		finally:
			if temp_dir:
				shutil.rmtree(temp_dir, ignore_errors=True)
