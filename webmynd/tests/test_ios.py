import mock
from nose.tools import raises

from webmynd import ForgeError
from webmynd.ios import IOSRunner
from webmynd.tests import dummy_config, lib

class TestIOSRunner(object):

	@raises(ForgeError)
	@mock.patch('webmynd.ios.path')
	def test_sdk_not_present(self, path):
		path.exists.return_value = False
		IOSRunner()
