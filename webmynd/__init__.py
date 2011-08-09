import sys

VERSION = '0.2.4pre'

if sys.hexversion < 0x020600f0:
	raise Exception('WebMynd tools require Python at least version 2.6.0: please update your interpreter')

from main import *
