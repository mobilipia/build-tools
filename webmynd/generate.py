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

LOG = logging.getLogger(__name__)

def _read_encoded_file(f_name, encoding='utf8'):
	with codecs.open(f_name, 'r', encoding=encoding) as in_file:
		try:
			return in_file.read()
		except UnicodeDecodeError:
			LOG.error('%s is not a valid UTF-8 encoded file: please convert it' % f_name)
			raise

class Generate(object):
	'Local re-creation of files that are dependent on user code'
	def __init__(self, app_config_file, **kw):
		'''
		:param app_config: app configuration dictionary
		'''
		app_config_s = _read_encoded_file(app_config_file)
		self.app_config = json.loads(app_config_s)
	
	def all(self, target_dir, user_dir):
		'''Re-create all local files in built targets
		
		:param target_dir: the parent directory of the per-platform builds
		:param user_dir: the directory holding user's code
		'''
		if path.isdir(user_dir):
			self.user(user_dir)
		if path.isdir(path.join(target_dir, 'firefox')):
			self.firefox(target_dir, user_dir)
		if path.isdir(path.join(target_dir, 'chrome')):
			self.chrome(target_dir, user_dir)
                if path.isdir(path.join(target_dir, 'webmynd.safariextension')):
                    self.safari(target_dir, user_dir)
	
	def user(self, user_dir):
		'''Find and replace ``${uuid}`` with the real UUID
		
		:param user_dir: the parent of files to look inside
		'''
		uuid = self.app_config['uuid']
		find = '${uuid}'
		
		for root, _, files in os.walk(user_dir):
			for f_name in [path.abspath(path.join(root, f)) for f in files]:
				if f_name.split('.')[-1] in ('html', 'htm', 'js', 'css'):
					LOG.debug('replacing "%s" with "%s" in %s' % (find, uuid, f_name))
					in_file_contents = _read_encoded_file(f_name)
					in_file_contents = in_file_contents.replace(find, uuid)
					
					with codecs.open(f_name, 'w', encoding='utf8') as out_file:
						out_file.write(in_file_contents)
	
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
		overlay = _read_encoded_file(overlay_filename)
		
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
			bg_file_s = _read_encoded_file(bg_filename)
			all_bg_files.write('\n'+bg_file_s)
		
		marker = 'window.__WEBMYND_MARKER=1;'
		LOG.debug("replacing %s with %s" % (marker, 'concatenated background files'))
		
		new_overlay = overlay.replace(marker, all_bg_files.getvalue())
		
		with codecs.open(overlay_filename, 'w', encoding='utf8') as out_file:
			out_file.write(new_overlay)
		LOG.info('re-generated overlay.js')
	
	def chrome(self, target_dir, user_dir):
		'''Ensure that ``data.js`` is in Chome's customer code directory.'''
		LOG.debug('copying data.js from common directory into user code')
		shutil.copy(path.join(target_dir, 'chrome', 'common', 'data.js'), path.join(user_dir, 'data.js'))
   
        def safari(self, target_dir, user_dir):
            '''Copy over icons if they exist'''
            LOG.debug('copying icons for Safari')
            if (self.app_config["icons"]["32"]):
                shutil.copy(path.join(user_dir, self.app_config["icons"]["32"]), 
                    path.join(target_dir, 'webmynd.safariextension', 'icon-32.png')) 
            if (self.app_config["icons"]["32"]):
                shutil.copy(path.join(user_dir, self.app_config["icons"]["32"]), 
                    path.join(target_dir, 'webmynd.safariextension', 'icon-32.png'))
            if (self.app_config["icons"]["32"]):
                shutil.copy(path.join(user_dir, self.app_config["icons"]["32"]), 
                path.join(target_dir, 'webmynd.safariextension', 'icon-32.png'))
