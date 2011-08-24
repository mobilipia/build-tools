'''WebMynd Build Tools'''
import sys

VERSION = '1'

def _check_version():
	'''Throw error if we're on Python < 2.6'''
	if sys.hexversion < 0x020600f0:
		raise Exception('WebMynd tools require Python at least version 2.6.0: please update your interpreter')
_check_version()