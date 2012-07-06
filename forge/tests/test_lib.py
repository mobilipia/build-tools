import os
from os import path
import shutil
import tempfile
import subprocess

from mock import patch
import mock
from nose.tools import eq_

from forge import lib


class TestUnzipWithPermissions(object):

	@patch('forge.lib.PopenWithoutNewConsole')
	def test_when_system_has_unzip_should_call_unzip(self, Popen):
		Popen.return_value.communicate.return_value = ('stdout', 'stderr')
		lib.unzip_with_permissions('dummy archive.zip')
		Popen.assert_called_with(
				["unzip", "-o", "dummy archive.zip", "-d", "."],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		eq_(Popen.call_count, 2)

	@patch('forge.lib.zipfile.ZipFile')
	@patch('forge.lib.extract_zipfile')
	@patch('forge.lib.PopenWithoutNewConsole')
	def test_when_system_doesnt_have_unzip_should_use_zipfile(self, Popen, extract_zipfile, ZipFile):
		Popen.side_effect = OSError("cant find unzip")
		zip_object = mock.Mock()
		ZipFile.return_value = zip_object

		lib.unzip_with_permissions('dummy archive.zip')

		eq_(Popen.call_count, 1)
		ZipFile.assert_called_once_with('dummy archive.zip')
		extract_zipfile.assert_called_once_with(zip_object, '.')
		zip_object.close.assert_called_once_with()


class TestPlatformChangeset(object):
	def setup(self):
		self.tdir = tempfile.mkdtemp()
		self.orig_dir = os.getcwd()
		os.chdir(self.tdir)

		os.makedirs(path.join('.template', 'lib'))
		with open(path.join('.template', 'lib', 'changeset.txt'), 'w') as changeset_f:
			changeset_f.write("0123456789AB")
	
	def teardown(self):
		os.chdir(self.orig_dir)
		shutil.rmtree(self.tdir, ignore_errors=True)

	def test_read_changeset(self):
		eq_(lib.platform_changeset(), '0123456789AB')


class TestClassifyPlatform(object):
	_stable_version = 'v1.3'
	
	def test_no_v_at_start_is_non_standard(self):
		eq_(lib.classify_platform(self._stable_version, '1.2'), 'nonstandard')
		eq_(lib.classify_platform(self._stable_version, 'hello_world'), 'nonstandard')

	def test_v_and_three_parts_is_minor(self):
		eq_(lib.classify_platform(self._stable_version, 'v1.2.3'), 'minor')

	def test_staging_branch_is_nonstandard(self):
		eq_(lib.classify_platform(self._stable_version, 'v1.3_staging'), 'nonstandard')

	def test_one_major_version_less_is_old(self):
		eq_(lib.classify_platform(self._stable_version, 'v1.2'), 'old')
