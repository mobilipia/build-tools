import os
from os import path
import shutil
import tempfile

from mock import patch
import mock
from nose.tools import eq_

from forge import lib

class TestUnzipWithPermissions(object):

	@patch('forge.lib.subprocess')
	def test_when_system_has_unzip_should_call_unzip(self, subprocess):
		subprocess.Popen.return_value.communicate.return_value = ('stdout', 'stderr')
		lib.unzip_with_permissions('dummy archive.zip')
		subprocess.Popen.assert_called_with(["unzip", "-o", "dummy archive.zip"],
				stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		eq_(subprocess.Popen.call_count, 2)

	@patch('forge.lib.subprocess')
	@patch('forge.lib.zipfile.ZipFile')
	@patch('forge.lib.extract_zipfile')
	def test_when_system_doesnt_have_unzip_should_use_zipfile(self, extract_zipfile, ZipFile, subprocess):
		subprocess.Popen.side_effect = OSError("cant find unzip")
		zip_object = mock.Mock()
		ZipFile.return_value = zip_object

		lib.unzip_with_permissions('dummy archive.zip')

		eq_(subprocess.Popen.call_count, 1)
		ZipFile.assert_called_once_with('dummy archive.zip')
		extract_zipfile.assert_called_once_with(zip_object)
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
