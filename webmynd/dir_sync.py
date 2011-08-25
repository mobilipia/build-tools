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
class ToDirectoryMissing(SyncError):
	'A directory is missing in the "target" directory'
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
		uuid = self.config.get('main.uuid')
		self._target_dirs = [path.join(d, uuid) for d in (
				path.join('development', 'chrome'),
				path.join('development', 'firefox'),
				path.join('development', 'webmynd.safariextension'),
			) if path.isdir(d)
		]
	
	def user_to_target(self, force=False):
		'''Ensure that all files in the ``user`` directory have been hardlinked
		to the right place in platforms' folders.
		
		:param force: ignore and overwrite any changes in the target directories **USE WITH CAUTION**
		'''
		LOG.info('syncing %s to %s' % (self._user_dir, self._target_dirs))
		if force:
			for to_ in self._target_dirs:
				shutil.rmtree(to_, ignore_errors=True)
				os.mkdir(to_)
				LOG.debug('cleaned out "%s" directory' % to_)
			
		if not path.isdir(self._user_dir):
			raise FromDirectoryMissing('"%s" directory must exist to proceed' % self._user_dir)
		for to_ in self._target_dirs:
			if not path.isdir(to_):
				raise ToDirectoryMissing('"%s" directory must exist to proceed' % to_)
				
		self._errors = []
		
		for target_dir in self._target_dirs:
			LOG.debug('comparing %s and %s' % (self._user_dir, target_dir))
			comp = filecmp.dircmp(self._user_dir, target_dir, ignore=[])
			self._errors += self._process_comparison(target_dir, self._user_dir, '', comp)

		# checking finished - any problems?
		if self._errors:
			for msg in self._errors:
				LOG.error(msg)
			raise Exception('Your WebMynd code has not been structured correctly')
		LOG.info('user_to_target completed successfully')

	def _process_comparison(self, root_dir, from_dir, sub_dir, comp, count=0):
		'Check the given directory comparison for differences, fixing where possible'
		if count > 500:
			raise Exception('recursion limit exceeded for _sync')
		errors = []
		if comp.left_only:
			for thing in comp.left_only:
				user_thing = path.join(from_dir, sub_dir, thing)
				target_thing = path.join(root_dir, sub_dir, thing)
				if path.isdir(user_thing):
					LOG.info('creating "%s" directory' % (target_thing))
					os.mkdir(target_thing)
					LOG.info('recomparing directories...')
					new_comp = filecmp.dircmp(path.join(from_dir, sub_dir), path.join(root_dir, sub_dir))
					return self._process_comparison(root_dir, from_dir, sub_dir, new_comp, count+1)
				elif path.isfile(user_thing):
					LOG.info('linking %s to %s' % (user_thing, target_thing))
					os.link(user_thing, target_thing)
				else:
					errors.append("Don't know how to handle %s" % user_thing)
				
		if comp.right_only:
			errors.append('''These files only exist in %s.
Either remove them or copy them to %s:
\t%s''' % (root_dir, from_dir, '\n\t'.join(comp.right_only)))
			
		if comp.common_funny or comp.funny_files:
			errors.append('''Could not compare these files in %s and %s.
Unable to proceed:
\t%s''' % (root_dir, from_dir, '\n\t'.join(comp.common_funny + comp.funny_files)))
			
		if comp.diff_files:
			errors.append('''These files differ in %s and %s.
Either remove the version in %s or ensure the right content is in both files:
\t%s''' % (root_dir, from_dir, root_dir, '\n\t'.join(comp.diff_files)))

		for directory, sub_comp in comp.subdirs.iteritems():
			LOG.debug('checking subdirectory "%s"' % directory)
			self._process_comparison(root_dir, from_dir, path.join(sub_dir, directory), sub_comp, count+1)
			
		return errors