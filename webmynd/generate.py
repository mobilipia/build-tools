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

LOG = logging.getLogger(__name__)

class Generate(object):
	'Local re-creation of files that are dependent on user code'
	def __init__(self, app_config_file, **kw):
		'''
		:param app_config: app configuration dictionary
		'''
		with codecs.open(app_config_file, encoding='utf8') as app_config:
			self.app_config = json.load(app_config)
			
	def all(self, target_dir, user_dir):
		'''Re-create all local files in built targets
		
		:param target_dir: the parent directory of the per-platform builds
		:param user_dir: the directory holding user's code
		'''
		temp_d = tempfile.mkdtemp()
		try:
			if path.isdir(user_dir):
				self.user(temp_d, user_dir)
			if path.isdir(path.join(target_dir, 'firefox')):
				self.firefox(target_dir, temp_d)
			if path.isdir(path.join(target_dir, 'chrome')):
				self.chrome(target_dir, temp_d)
			if path.isdir(path.join(target_dir, 'android')):
				self.android(target_dir, temp_d)
		finally:
			shutil.rmtree(temp_d)
		
	def user(self, target_dir, user_dir):
		'''Find and replace ``${uuid}`` with the real UUID
		
		:param user_dir: the parent of files to look inside
		'''
		uuid = self.app_config['uuid']
		find = '${uuid}'
		
		for root, _, files in os.walk(user_dir):
			for f in files:
				in_dir = root
				out_dir = target_dir+root[len(user_dir):]
				if not os.path.exists(out_dir):
					os.makedirs(out_dir)
				
				if f.split('.')[-1] in ('html', 'js'):
					with codecs.open(path.join(in_dir,f), 'r', encoding='utf8') as in_file:
						in_file_contents = in_file.read()
						in_file_contents = in_file_contents.replace(find, uuid)
						LOG.debug('replacing "%s" with "%s" in %s' % (find, uuid, path.join(in_dir,f)))
						if f.split('.')[-1] == 'js':
							in_file_contents = '(function(){var uuid="'+uuid+'";window.webmynd=window.webmynd||{};window.webmynd[uuid]=window.webmynd[uuid]||{};window.webmynd[uuid].onLoad=window.webmynd[uuid].onLoad||[];window.webmynd[uuid].onLoad.push(function(api){'+in_file_contents+'});window.webmynd[uuid].hasLoaded&&window.webmynd[uuid].hasLoaded()})();'
							LOG.debug('Wrapping javascript in %s' % path.join(in_dir,f))
					with codecs.open(path.join(out_dir,f), 'w', encoding='utf8') as out_file:
						out_file.write(in_file_contents)
				else:
					shutil.copyfile(path.join(in_dir,f), path.join(out_dir,f))
		
	def firefox(self, target_dir, user_dir):
		'''Re-create overlay.js for Firefox from source files.
		
		Firefox expects all "privileged" files to be present in one mega-script:
		we will combine the user-defined files together into one.
		
		:param target_dir: the output directory
		:param user_dir: the directory to read the source files from
		'''
		background_files = self.app_config['background_files']
		
		overlay_filename = path.join(target_dir, 'firefox', 'content', 'overlay.js')
		LOG.debug('reading in "%s"' % overlay_filename)
		with codecs.open(overlay_filename, encoding='utf8') as overlay_f:
			overlay = overlay_f.read()
		
		all_bg_files = StringIO()
		for bg_filename in background_files:
			if bg_filename.startswith('http://') or bg_filename.startswith('https://'):
				# ignore remote script - pointed at elsewhere
				___a = 1 # trigger coverage
				continue
			bg_filename = path.join(user_dir, bg_filename.lstrip('/'))
			if not path.isfile(bg_filename):
				raise Exception('Your "background_files" settings points at "%s", '
					'but it doesn\'t exist' % bg_filename)
			LOG.debug('reading in "%s"' % bg_filename)
			with codecs.open(bg_filename, encoding='utf8') as bg_file:
				all_bg_files.write('\n'+bg_file.read())
		
		marker = 'window.__WEBMYND_MARKER=1;'
		LOG.debug("replacing %s with %s" % (marker, 'concatenated background files'))

		new_overlay = overlay.replace(marker, all_bg_files.getvalue())

		with codecs.open(overlay_filename, 'w', encoding='utf8') as out_file:
			out_file.write(new_overlay)
		LOG.info('re-generated overlay.js')
		
	def chrome(self, target_dir, user_dir):
		uuid = self.app_config['uuid']
		chrome_user_dir = path.join(target_dir, 'chrome', uuid)
		LOG.debug("Copying user dir to chrome")
		shutil.copytree(user_dir, chrome_user_dir)

	def android(self, target_dir, user_dir):
		uuid = self.app_config['uuid']
		android_user_dir = path.join(target_dir, 'android', 'assets')
		LOG.debug("Copying user dir to android")
		first = 0;
		for file in os.listdir(user_dir):
			if os.path.isdir(path.join(user_dir, file)):
				shutil.copytree(path.join(user_dir, file), path.join(android_user_dir, file))
			else:
				shutil.copyfile(path.join(user_dir, file), path.join(android_user_dir, file))