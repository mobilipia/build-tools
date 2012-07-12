'''Forge Build Tools'''
import sys


VERSION = '3.3.5'

def _check_version():
	'''Throw error if we're not on Python 2.7'''
	if not 0x020700f0 <= sys.hexversion < 0x02080000:
		raise Exception('Forge tools require Python 2.7.0: please update your interpreter')

_check_version()


class ForgeError(Exception):
	pass

from forge import async


def get_version():
	return VERSION


settings = {}

def request_username():
	if 'username' not in settings:
		event_id = async.current_call().emit('question', schema={
			'description': 'Login with the Forge service',
			'properties': {
				'username': {
					'type': 'string',
					'title': 'Username',
					'description': 'This is the email address you used to sign up to trigger.io.'
				}
			}
		})

		settings['username'] = async.current_call().wait_for_response(event_id)['data']['username']

	return settings['username']


def request_password():
	if 'password' not in settings:
		event_id = async.current_call().emit('question', schema={
			'description': 'Login with the Forge service',
			'properties': {
				'password': {
					'type': 'string',
					'title': 'Password',
					'description': 'The password you use to login to trigger.io.',
					'_password': True
				}
			}
		})
		settings['password'] = async.current_call().wait_for_response(event_id)['data']['password']

	return settings['password']
