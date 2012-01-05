'''Forge Build Tools'''
from getpass import getpass
import sys
from os import path

VERSION = '2.3.1'

def _check_version():
	'''Throw error if we're on Python < 2.6'''
	if sys.hexversion < 0x020600f0:
		raise Exception('Forge tools require Python at least version 2.6.0: please update your interpreter')
_check_version()

class ForgeError(Exception):
	pass

def _get_commit_count():
	# XXX: this requires the forge library to be located a specific distance from
	# the forge tools folder
	# might make sense for this value to be obtained from an environment variable which
	# is set by all entry points
	forge_root = path.abspath(path.join(__file__, "..", ".."))
	git_folder = path.join(forge_root, '.git')

	if path.exists(git_folder):
		try:
			from dulwich.repo import Repo
			forge_repo = Repo(forge_root)
			commit_count = len(forge_repo.revision_history(forge_repo.head()))
			return commit_count
		except ImportError:
			pass

def get_version():
	version = VERSION
	commit_count = _get_commit_count()
	if commit_count is not None:
		version += ".{commit_count}".format(commit_count=_get_commit_count())

	return version

settings = {}

def request_username():
	if 'username' not in settings:
		# TODO: detect context, e.g. webapp, console app
		settings['username'] = raw_input("Your email address: ")

	return settings['username']

def request_password():
	if 'password' not in settings:
		# TODO: detect context, e.g. webapp, console app
		settings['password'] = getpass()

	return settings['password']
