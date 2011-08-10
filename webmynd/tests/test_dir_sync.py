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
		for target_dir in self.dir_sync._target_dirs:
			ok_(path.isdir(path.join(target_dir, 'user-only-dir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-dir-file')))
			ok_(path.isdir(path.join(target_dir, 'user-only-dir', 'user-only-subdir')))
			ok_(path.isfile(path.join(target_dir, 'user-only-dir', 'user-only-subdir', 'user-only-subdir-file')))
			
			def file_test(*f_path, **kw):
				match = kw.get('match', True)
				with open(path.join(self.dir_sync._user_dir, *f_path)) as frm_file:
					with open(path.join(target_dir, *f_path)) as to_file:
						(eq_ if match else assert_not_equals)(frm_file.read(), to_file.read())
			
			file_test('common')
			file_test('non-match', match=False)
			file_test('user-only-dir', 'user-only-dir-file')
			file_test('user-only-dir', 'user-only-subdir', 'user-only-subdir-file')

	@mock.patch('webmynd.dir_sync.path')
	@mock.patch('webmynd.dir_sync.os')
	@mock.patch('webmynd.dir_sync.shutil')
	def test_force(self, shutil, os, path):
		path.isdir.return_value = False
		assert_raises_regexp(webmynd.dir_sync.FromDirectoryMissing, 'directory must exist to proceed',
			self.dir_sync.user_to_target, True)
		eq_(shutil.rmtree.call_count, 2)
		eq_(os.mkdir.call_count, 2)

class Test_ProcessComparison(object):
	def setup(self):
		self.test_config = Config._test_instance()
		self.dir_sync = DirectorySync(self.test_config)
		self.comp = mock.Mock()
		self.comp.left_only = []
		self.comp.right_only = []
		self.comp.common_funny = []
		self.comp.funny_files = []
		self.comp.diff_files = []
		self.comp.subdirs = {}
		
	def test_no_problems(self):
		errors = self.dir_sync._process_comparison(
			'dummy root', 'dummy frm', 'dummy sub', self.comp
		)
		eq_(len(errors), 0)
		
	@mock.patch('webmynd.dir_sync.filecmp')
	@mock.patch('webmynd.dir_sync.os')
	@mock.patch('webmynd.dir_sync.path')
	def test_too_deep_dir(self, path, os, filecmp):
		path.isdir.return_value = True
		self.comp.left_only = ['dummy thing']
		filecmp.dircmp.return_value = self.comp
		
		assert_raises_regexp(Exception, 'recursion limit',
			self.dir_sync._process_comparison, 'dummy root', 'dummy frm', 'dummy sub', self.comp
		)
		
		ok_(os.mkdir.call_count > 500)
		ok_(path.isdir.call_count > 500)
		
	@mock.patch('webmynd.dir_sync.os')
	@mock.patch('webmynd.dir_sync.path')
	def test_link_file(self, path, os):
		path.isdir.return_value = False
		path.isfile.return_value = True
		self.comp.left_only = ['dummy thing']
		joins = ['first join', 'second join']
		def joins_eff(*args, **kw):
			return joins.pop(0)
		path.join.side_effect = joins_eff
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 0)
		os.link.assert_called_once_with('first join', 'second join')
		
	@mock.patch('webmynd.dir_sync.path')
	def test_not_a_dir_or_file(self, path):
		path.isdir.return_value = False
		path.isfile.return_value = False
		self.comp.left_only = ['dummy thing']
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 1)
		
	@mock.patch('webmynd.dir_sync.path')
	def test_right_only(self, path):
		self.comp.right_only = ['1', '2']
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 1)
		ok_(errors[0].index('only exist in dummy root') > -1)
		ok_(errors[0].index('1\n\t2') > -1)
		
	@mock.patch('webmynd.dir_sync.path')
	def test_funny(self, path):
		self.comp.common_funny = ['1']
		self.comp.funny_files = ['2']
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 1)
		ok_(errors[0].index('not compare these files') > -1)
		ok_(errors[0].index('1\n\t2') > -1)
		
	@mock.patch('webmynd.dir_sync.path')
	def test_diff(self, path):
		self.comp.diff_files = ['1', '2']
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 1)
		ok_(errors[0].index('differ in dummy root and dummy frm') > -1)
		ok_(errors[0].index('1\n\t2') > -1)
		
	@mock.patch('webmynd.dir_sync.path')
	def test_subdir(self, path):
		sub_comp = mock.Mock()
		sub_comp.subdirs.iteritems.return_value = ()
		sub_comp.left_only = []
		sub_comp.right_only = []
		sub_comp.common_funny = []
		sub_comp.funny_files = []
		sub_comp.diff_files = []

		del self.comp.subdirs
		self.comp.subdirs.iteritems.return_value = (('sub directory', sub_comp),)
		
		errors = self.dir_sync._process_comparison('dummy root', 'dummy frm', 'dummy sub', self.comp)
		
		eq_(len(errors), 0)
		path.join.call_args_list
		
class TestUserToTarget2(object):
	@mock.patch('webmynd.dir_sync.filecmp')
	@mock.patch('webmynd.dir_sync.path')
	def test_normal(self, path, filecmp):
		path.isdir.return_value = True
		self.test_config = Config._test_instance()
		self.dir_sync = DirectorySync(self.test_config)
		self.dir_sync._process_comparison = mock.Mock()
		self.dir_sync._process_comparison.return_value = []
		self.dir_sync._user_dir = 'dummy frm'
		self.dir_sync._target_dirs = ['dummy to 1', 'dummy to 2']
		
		self.dir_sync.user_to_target(False)
		
		eq_(self.dir_sync._process_comparison.call_args_list, [
			(('dummy to 1', 'dummy frm', '', filecmp.dircmp.return_value), {}),
			(('dummy to 2', 'dummy frm', '', filecmp.dircmp.return_value), {}),
		])