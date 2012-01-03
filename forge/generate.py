'''\
To avoid having to perform a full build every time the user makes a change to
their source, we can re-create some files locally.

This greatly speeds up the development process, and enables offline development
in simple situations.
'''
from __future__ import with_statement

import codecs
import json
import logging
from StringIO import StringIO
import os
from os import path
import shutil
import tempfile
import sys
from glob import glob

from forge import build, build_config
from forge.build import import_generate_dynamic
from forge.lib import walk2

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

	def __init__(self, app_config_file, **kw):
		'''
		:param app_config_file: file containing the JSON app configuration
		'''
		self.app_config = build_config.load_app(app_config_file)

	def all(self, target_dir, user_dir):
		'''Re-create all local files in built targets

		:param target_dir: the parent directory of the per-platform builds
		:param user_dir: the directory holding user's code
		'''
		build_to_run = build.create_build(target_dir)
		generate_dynamic = import_generate_dynamic()

		build_to_run.add_steps(generate_dynamic.customer_phases.resolve_urls())
		build_to_run.add_steps(generate_dynamic.customer_phases.copy_user_source_to_template(server=False))
		build_to_run.add_steps(generate_dynamic.customer_phases.include_platform_in_html(server=False))
		build_to_run.add_steps(generate_dynamic.customer_phases.include_icons())

		build_to_run.run()