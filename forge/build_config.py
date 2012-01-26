import codecs
import json
import logging
from os import path

import forge
from forge import defaults

LOG = logging.getLogger(__name__)

def load(filename=None, expect_app_config=True):
	'''Read in and JSON the app-indendent configuration file (normally forge_build.json)
	
	:param expect_app_config: should we panic if the app config (normally src/config.json) doesn't exist?
	'''
	if filename is None:
		filename = defaults.CONFIG_FILE

	with open(filename) as conf_file:
		config = json.load(conf_file)
	
	try:
		config['uuid'] = load_app()['uuid']
	except IOError:
		if expect_app_config:
			# i.e. app config should be there, but isn't
			raise IOError('no app configuration file found at {0}'.format(defaults.APP_CONFIG_FILE))
	except KeyError:
		raise IOError('no "uuid" key found in your app configuration')

	LOG.debug('Forge build tools version: %s' % forge.get_version())
	for key, val in config.iteritems():
		LOG.debug('%s: %s' % (key, json.dumps(val)))

	return config

def load_app():
	'''Read in and JSON parse the per-app configuration file (src/config.json)
	and identify JSON file (src/identity.json)
	'''
	app_config_file = defaults.APP_CONFIG_FILE

	with codecs.open(app_config_file, encoding='utf8') as app_config:
		try:
			config = json.load(app_config)
		except ValueError as e:
			raise forge.ForgeError("Your configuration file ({0}) is malformed:\n{1}".format(app_config_file, e))
	
	identity_file = defaults.IDENTITY_FILE
	
	with codecs.open(identity_file, encoding='utf8') as identity:
		try:
			identity_config = json.load(identity)
		except ValueError as e:
			raise forge.ForgeError("Your identity file ({0}) is malformed:\n{1}".format(identity_file, e))
	
	config.update(identity_config)
	return config