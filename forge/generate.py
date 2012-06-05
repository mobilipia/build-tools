'''\
To avoid having to perform a full build every time the user makes a change to
their source, we can re-create some files locally.

This greatly speeds up the development process, and enables offline development
in simple situations.
'''
from __future__ import with_statement

import codecs
import logging

from forge import build_config
from forge.build import create_build, import_generate_dynamic

LOG = logging.getLogger(__name__)

def _read_encoded_file(f_name, encoding='utf8'):
	with codecs.open(f_name, 'r', encoding=encoding) as in_file:
		try:
			return in_file.read()
		except UnicodeDecodeError:
			LOG.error('%s is not a valid UTF-8 encoded file: please convert it' % f_name)
			raise

class Generate(object):
	'Local re-creation of files, based on server-supplied instructions'

	def __init__(self, **kw):
		self.app_config = build_config.load_app()

	def all(self, target_dir, user_dir, extra_args, config=None):
		'''Re-create all local files in built targets

		:param target_dir: the parent directory of the per-platform builds
		:param user_dir: the directory holding user's code
		'''
		generate_dynamic = import_generate_dynamic()
		build_to_run = create_build(
			target_dir,
			config=config,
			extra_args=extra_args,
		)
		
		generate_dynamic.customer_goals.generate_app_from_template(
			generate_module=generate_dynamic,
			build_to_run=build_to_run,
			server=False,
		)
