import mock

import webmynd
from lib import assert_raises_regexp

@mock.patch('webmynd.sys')
def test__check_version_old(sys):
	sys.hexversion = 0x0205FFFF
	assert_raises_regexp(Exception, 'please update your interpreter', webmynd._check_version)
