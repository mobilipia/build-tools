import os
from os import path
import re
import shutil
import tarfile
import tempfile
import zipfile

from nose.tools import raises, assert_raises_regexp, assert_equals, assert_not_equals, assert_true, assert_false

import webmynd
from webmynd import DirectorySync, BuildConfig, defaults

class TestDirectorySync(object):
	TEST_ARCHIVE = 'test_user_to_target.tgz'
	
	def setup(self):
		self.orig_dir = os.getcwd()
		self.working_dir = tempfile.mkdtemp()
		os.chdir(self.working_dir)
		tar = tarfile.open(
			name=path.join(path.dirname(__file__), self.TEST_ARCHIVE),
			mode='r')
		tar.extractall()
		self.test_config = BuildConfig._test_instance()
		self.dir_sync = DirectorySync(self.test_config)

	def teardown(self):
		os.chdir(self.orig_dir)
		shutil.rmtree(self.working_dir, ignore_errors=True)
		del self.dir_sync
		
class TestUserToTarget(TestDirectorySync):
	TEST_ARCHIVE = 'test_user_to_target.tgz'
	
	@raises(webmynd.dir_sync.FromDirectoryMissing)
	def test_no_user(self):
		shutil.rmtree(defaults.USER_dir)
		self.dir_sync.user_to_target()
		
	@raises(webmynd.dir_sync.ToDirectoryMissing)
	def test_no_chrome(self):
		shutil.rmtree(path.join('development', 'chrome'))
		self.dir_sync.user_to_target()
	
	def test_normal(self):
		assert_raises_regexp(Exception,
			'^Your WebMynd code has not been structured correctly$',
			self.dir_sync.user_to_target
		)
		assert_equals(len(self.dir_sync._errors), 3)
		for target_dir in self.dir_sync.TARGET_DIRS:
			assert_true(path.isdir(path.join(target_dir, 'user-only-dir')))
			assert_true(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-dir-file')))
			assert_true(path.isdir(path.join(target_dir, 'user-only-dir', 'user-only-subdir')))
			assert_true(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-subdir', 'user-only-subdir-file')))
			
			def file_test(*f_path, **kw):
				match = kw.get('match', True)
				with open(path.join(self.dir_sync.USER_DIR, *f_path)) as frm_file:
					with open(path.join(target_dir, *f_path)) as to_file:
						(assert_equals if match else assert_not_equals)(frm_file.read(), to_file.read())
			
			file_test('common')
			file_test('non-match', match=False)
			file_test('user-only-dir', 'user-only-dir-file')
			file_test('user-only-dir', 'user-only-subdir', 'user-only-subdir-file')