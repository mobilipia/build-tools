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

from webmynd import build_config

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
		self.app_config = build_config.load_app(app_config_file)
			
	def all(self, target_dir, user_dir):
		'''Re-create all local files in built targets
		
		:param target_dir: the parent directory of the per-platform builds
		:param user_dir: the directory holding user's code
		'''
		if path.isdir(path.join(target_dir, 'firefox')):
			self.firefox(target_dir, user_dir)
		if path.isdir(path.join(target_dir, 'chrome')):
			self.chrome(target_dir, user_dir)
		if path.isdir(path.join(target_dir, 'webmynd.safariextension')):
			self.safari(target_dir, user_dir)
		if path.isdir(path.join(target_dir, 'android')):
			self.android(target_dir, user_dir)

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

	def safari(self, target_dir, user_dir):
		'''Copy over icons if they exist'''
		LOG.debug('copying icons for Safari')
		if "icons" in self.app_config:
			if "32" in self.app_config["icons"]:
				shutil.copy(path.join(user_dir, self.app_config["icons"]["32"]),
					path.join(target_dir, 'webmynd.safariextension', 'icon-32.png'))
	
	def chrome(self, target_dir, user_dir):
		uuid = self.app_config['uuid']
		chrome_user_dir = path.join(target_dir, 'chrome', uuid)
		LOG.debug("Copying user dir to chrome")
		
		find = "<head>"
		replace = "<head><script src='/webmynd/all.js'></script>"
		
		self._recursive_replace(user_dir, chrome_user_dir, ('html',), find, replace)

	def android(self, target_dir, user_dir):
		uuid = self.app_config['uuid']
		android_user_dir = path.join(target_dir, 'android', 'assets')
		LOG.debug("Copying user dir to android")
	
		find = "<head>"
		replace = "<head><script src='file:///android_asset/webmynd/all.js'></script>"
		
		self._recursive_replace(user_dir, android_user_dir, ('html',), find, replace)
	
	def _recursive_replace(self, parent, output_root, suffixes, find, replace):
		'''Recurse over a tree of files (under :param:`parent`), writing all files to an analagous structure under
		:param:`output_root`. In addition, for files with a names ending in .:param:`suffix`, instances of
		:param:`find` are replaced with :param:`replace`.

		:param parent: the top-level directory to look for files in
		:param output_root: top-level directory that the files will be written to
		:param suffixes: a collection of string suffixes of files to consider when replacing :param:`find` with :param:`replace`
		:param find: string to look for in the text
		:param replace: what to replace :param:`find` with before writing the output
		'''
		for root, _, files in os.walk(parent):
			for file_ in files:
				out_dir = output_root + root[len(parent):]
				if not os.path.exists(out_dir):
					os.makedirs(out_dir)
				
				if file_.rpartition('.')[2] in suffixes:
					self._replace_and_write_file(path.join(root, file_), path.join(out_dir, file_), find, replace)
				else:
					shutil.copyfile(path.join(root, file_), path.join(out_dir, file_))

	
	def _replace_and_write_file(self, in_filename, out_filename, find, replace):
		'''Read from :param:`in_filename`, write to :param:`out_filename`,
			replacing :param:`find` with :param:`replace` as we go.
			
		:param in_filename: the name of the input file
		:param out_filename: the name of the output file
		:param find: string to look for in the text
		:param replace: what to replace :param:`find` with before writing the output
		'''
		LOG.debug('replacing "%s" with "%s" in %s' % (find, replace, in_filename))
		with codecs.open(in_filename, 'r', encoding='utf8') as in_file:
			in_file_contents = in_file.read()
			in_file_contents = in_file_contents.replace(find, replace)
		with codecs.open(out_filename, 'w', encoding='utf8') as out_file:
			out_file.write(in_file_contents)
		