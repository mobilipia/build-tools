import subprocess
from mock import patch
import mock
from nose.tools import eq_

from forge import lib

class TestUnzipWithPermissions(object):

	@patch('forge.remote.subprocess.Popen')
	def test_when_system_has_unzip_should_call_unzip(self, Popen):
		Popen.return_value.communicate.return_value = ('stdout', 'stderr')
		lib.unzip_with_permissions('dummy archive.zip')
		Popen.assert_called_with(["unzip", "dummy archive.zip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		eq_(Popen.call_count, 2)

	@patch('forge.remote.subprocess.Popen')
	@patch('forge.remote.zipfile.ZipFile')
	@patch('forge.remote.lib.extract_zipfile')
	def test_when_system_doesnt_have_unzip_should_use_zipfile(self, extract_zipfile, ZipFile, Popen):
		Popen.side_effect = OSError("cant find unzip")
		zip_object = mock.Mock()
		ZipFile.return_value = zip_object

		lib.unzip_with_permissions('dummy archive.zip')

		eq_(Popen.call_count, 1)
		ZipFile.assert_called_once_with('dummy archive.zip')
		extract_zipfile.assert_called_once_with(zip_object)
		zip_object.close.assert_called_once_with()