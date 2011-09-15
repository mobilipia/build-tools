import mock
from nose.tools import raises, eq_, assert_not_equals, ok_
import os
from os import path
import shutil
import tarfile
import tempfile

import webmynd
from lib import assert_raises_regexp
from webmynd import defaults
from webmynd.dir_sync import DirectorySync
from webmynd.config import Config

class TestDirectorySync(object):
	def setup(self):
		self.orig_dir = os.getcwd()
		self.working_dir = tempfile.mkdtemp()
		os.chdir(self.working_dir)
		tar = tarfile.open(
			name=path.join(path.dirname(__file__), self.TEST_ARCHIVE),
			mode='r')
		tar.extractall()
		self.test_config = Config._test_instance()
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
		
	def test_normal(self):
		self.dir_sync.user_to_target()
		for target_dir in self.dir_sync._target_dirs:
			ok_(path.isdir(path.join(target_dir, 'user-only-dir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-dir-file')))
			ok_(path.isdir(path.join(target_dir, 'user-only-dir', 'user-only-subdir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-subdir', 'user-only-subdir-file')))
			
			def file_test(*f_path, **kw):
				with open(path.join(self.dir_sync._user_dir, *f_path)) as frm_file:
					with open(path.join(target_dir, *f_path)) as to_file:
						eq_(frm_file.read(), to_file.read())
			
			file_test('common')
			file_test('non-match')
			file_test('user-only-dir', 'user-only-dir-file')
			file_test('user-only-dir', 'user-only-subdir', 'user-only-subdir-file')

class TestUserToTarget2(object):
	@mock.patch('webmynd.dir_sync.shutil')
	@mock.patch('webmynd.dir_sync.path')
	def test_normal(self, path, shutil):
		path.isdir.return_value = True
		self.test_config = Config._test_instance()
		self.dir_sync = DirectorySync(self.test_config)
		self.dir_sync._user_dir = 'dummy frm'
		self.dir_sync._target_dirs = ['dummy to 1', 'dummy to 2']
		
		self.dir_sync.user_to_target()

		# should be called N times in __init__, once checking user dir
		eq_(len(path.isdir.call_args_list), len(self.dir_sync._target_dirs) + 1)
		eq_([call[0][0] for call in shutil.rmtree.call_args_list], self.dir_sync._target_dirs)
		eq_([call[0] for call in shutil.copytree.call_args_list], [(self.dir_sync._user_dir, to_) for to_ in self.dir_sync._target_dirs])