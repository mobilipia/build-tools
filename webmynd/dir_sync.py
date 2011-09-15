'Restore consistency between directories'
import filecmp
import logging
import os
from os import path
import shutil

from webmynd import defaults

LOG = logging.getLogger(__name__)

class SyncError(Exception):
	'Generic error during syncing'
	pass
class FromDirectoryMissing(SyncError):
	'A directory is missing in the "user" directory'
	pass
class DirectorySync(object):
	'Restore consistency between a "user" directory and a number of "target" directories'
	def __init__(self, config):
		'''
		:param config: system configuration
		:type config: :class:`~webmynd.config.Config`
		'''
		super(DirectorySync, self).__init__()
		self.config = config
		self._user_dir = path.abspath(defaults.USER_DIR)
		uuid = self.config.get('uuid')
		self._target_dirs = [path.join(d, uuid) for d in (
				path.join('development', 'chrome'),
				path.join('development', 'webmynd.safariextension'),
			) if path.isdir(d)
		]
	
	def user_to_target(self):
		'''Copy all files in the ``user`` directory to the relevant target directories.
		
		**CAUTION**: destructive to the target directories!
		'''
		LOG.info('copying %s to %s' % (self._user_dir, self._target_dirs))

		if not path.isdir(self._user_dir):
			raise FromDirectoryMissing('"%s" directory must exist to proceed' % self._user_dir)

		for to_ in self._target_dirs:
			LOG.debug('cleaning out "%s" directory' % to_)
			shutil.rmtree(to_, ignore_errors=True)
			LOG.debug('copying user code to "%s" directory' % to_)
			shutil.copytree(self._user_dir, to_)
			
		