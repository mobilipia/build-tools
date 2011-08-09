import filecmp
import logging
import os
from os import path
import shutil

import defaults

log = logging.getLogger(__name__)

class SyncError(Exception):
	pass
class FromDirectoryMissing(SyncError):
	pass
class ToDirectoryMissing(SyncError):
	pass

class DirectorySync(object):
	def __init__(self, config):
		super(DirectorySync, self).__init__()
		self.config = config
		self.USER_DIR = path.abspath(defaults.USER_DIR)
		uuid = self.config.get('main.uuid')
		self.TARGET_DIRS = [path.join(d, uuid) for d in (
				path.join('development', 'chrome'),
				path.join('development', 'webmynd.safariextension'),
			) if path.isdir(d)
		]
	
	def user_to_target(self, force=False):
		'''Ensure that all files in the ``user`` directory have been hardlinked to the right place in platforms' folders.
		
		:param force: ignore and overwrite any changes in the target directories **USE WITH CAUTION**
		'''
		log.info('syncing %s to %s' % (self.USER_DIR, ', '.join(self.TARGET_DIRS)))
		return self._sync(self.USER_DIR, self.TARGET_DIRS, force=force)

	def _process_comparison(self, frm, root, sub, comp, count=0):
		'Check the given directory comparison for differences, fixing where possible'
		if count > 500:
			raise Exception('recursion limit exceeded for _sync')
		errors = []
		if comp.left_only:
			for thing in comp.left_only:
				user_thing = path.join(frm, sub, thing)
				target_thing = path.join(root, sub, thing)
				if path.isdir(user_thing):
					log.info('creating "%s" directory' % (target_thing))
					os.mkdir(target_thing)
					log.info('recomparing directories...')
					new_comp = filecmp.dircmp(path.join(frm, sub), path.join(root, sub))
					return self._process_comparison(frm, root, sub, new_comp, count+1)
				elif path.isfile(user_thing):
					log.info('linking %s to %s' % (user_thing, target_thing))
					os.link(user_thing, target_thing)
				else:
					errors.append("Don't know how to handle %s" % user_thing)
				
		if comp.right_only:
			errors.append('''These files only exist in %s.
Either remove them or copy them to %s:
\t%s''' % (root, frm, '\n\t'.join(comp.right_only)))
			
		if comp.common_funny or comp.funny_files:
			errors.append('''Could not compare these files in %s and %s.
Unable to proceed:
\t%s''' % (root, frm, '\n\t'.join(comp.common_funny + comp.funny_files)))
			
		if comp.diff_files:
			errors.append('''These files differ in %s and %s.
Either remove the version in %s or ensure the right content is in both files:
\t%s''' % (root, frm, root, '\n\t'.join(comp.diff_files)))

		for directory, sub_comp in comp.subdirs.iteritems():
			log.debug('checking subdirectory "%s"' % directory)
			self._process_comparison(frm, root, path.join(sub, directory), sub_comp, count+1)
			
		return errors
				
	def _sync(self, frm, tos, force):
		if force:
			for to in tos:
				shutil.rmtree(to, ignore_errors=True)
				os.mkdir(to)
				log.debug('cleaned out "%s" directory' % to)
			
		if not path.isdir(frm):
			raise FromDirectoryMissing('"%s" directory must exist to proceed' % frm)
		for to in tos:
			if not path.isdir(to):
				raise ToDirectoryMissing('"%s" directory must exist to proceed' % to)
				
		self._errors = []
		
		for target_dir in tos:
			log.debug('comparing %s and %s' % (frm, target_dir))
			comp = filecmp.dircmp(frm, target_dir, ignore=[])
			self._errors += self._process_comparison(frm, target_dir, '', comp)

		# checking finished - any problems?
		if self._errors:
			for msg in self._errors:
				log.error(msg)
			raise Exception('Your WebMynd code has not been structured correctly')
		log.info('_sync completed successfully')