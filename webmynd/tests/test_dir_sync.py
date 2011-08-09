import mock
from nose.tools import raises, eq_, assert_not_equals, ok_
import os
from os import path
import shutil
import tarfile
import tempfile

import webmynd
from lib import assert_raises_regexp
from webmynd import DirectorySync, BuildConfig, defaults

class TestDirectorySync(object):
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
		shutil.rmtree(defaults.USER_DIR)
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
		eq_(len(self.dir_sync._errors), 3)
		for target_dir in self.dir_sync.TARGET_DIRS:
			ok_(path.isdir(path.join(target_dir, 'user-only-dir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-dir-file')))
			ok_(path.isdir(path.join(target_dir, 'user-only-dir', 'user-only-subdir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-subdir', 'user-only-subdir-file')))
			
			def file_test(*f_path, **kw):
				match = kw.get('match', True)
				with open(path.join(self.dir_sync.USER_DIR, *f_path)) as frm_file:
					with open(path.join(target_dir, *f_path)) as to_file:
						(eq_ if match else assert_not_equals)(frm_file.read(), to_file.read())
			
			file_test('common')
			file_test('non-match', match=False)
			file_test('user-only-dir', 'user-only-dir-file')
			file_test('user-only-dir', 'user-only-subdir', 'user-only-subdir-file')

class Test_Sync(TestDirectorySync):
	TEST_ARCHIVE = 'test_user_to_target.tgz'
	@mock.patch('webmynd.dir_sync.os')
	@mock.patch('webmynd.dir_sync.shutil')
	def test_force(self, shutil, os):
		assert_raises_regexp(webmynd.dir_sync.FromDirectoryMissing, 'directory must exist to proceed',
			self.dir_sync._sync, 'from', ['to0', 'to1'], True)
		eq_(shutil.rmtree.call_count, 2)
		eq_(os.mkdir.call_count, 2)
	