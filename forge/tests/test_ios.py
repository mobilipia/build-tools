import mock
from nose.tools import raises, eq_

from forge import ForgeError
from forge.ios import IOSRunner
from forge.tests import dummy_config, lib

class TestIOSRunner(object):

	@raises(ForgeError)
	@mock.patch('forge.ios.path')
	def test_sdk_not_present(self, path):
		path.exists.return_value = False
		IOSRunner('dummy directory')
	
	
	@mock.patch('forge.ios.subprocess.Popen')
	def test_get_child_processes(self, Popen):
		ps_output = '''
 2  1
 3  2
 4  1
 5  11
'''.split('\n')
		Popen.return_value.stdout = ps_output
		
		result = IOSRunner.get_child_processes(1)
		
		eq_(result, [2, 4])