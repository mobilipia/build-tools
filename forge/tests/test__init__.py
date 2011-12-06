import mock

import forge
from lib import assert_raises_regexp

@mock.patch('forge.sys')
def test__check_version_old(sys):
	sys.hexversion = 0x0205FFFF
	assert_raises_regexp(Exception, 'please update your interpreter', forge._check_version)
