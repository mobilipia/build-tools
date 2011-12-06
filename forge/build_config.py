import codecs
import json
import logging
from os import path

import forge
from forge import defaults

LOG = logging.getLogger(__name__)

def load(filename=None):
	'Read in and JSON the app-indendent configuration file (normally forge_build.json)'
	if filename is None:
		filename = defaults.CONFIG_FILE
	
	with open(filename) as conf_file:
		config = json.load(conf_file)
	
	if path.exists(defaults.APP_CONFIG_FILE):
		LOG.debug('setting app UUID from %s' % defaults.APP_CONFIG_FILE)
		config['uuid'] = load_app(defaults.APP_CONFIG_FILE)['uuid']
	else:
		LOG.warning('no app configuration file found at %s' % defaults.APP_CONFIG_FILE)
	
	LOG.debug('Forge build tools version: %s' % forge.get_version())
	for key, val in config.iteritems():
		LOG.debug('%s: %s' % (key, json.dumps(val)))
	
	return config

def load_app(filename=None):
	'Read in and JSON parse the per-app configuration file (normall src/config.json)'
	if filename is None:
		filename = defaults.APP_CONFIG_FILE
	
	with codecs.open(filename, encoding='utf8') as app_config:
		try:
			return json.load(app_config)
		except ValueError as e:
			raise forge.ForgeError("Your configuration file ({0}) is malformed:\n{1}".format(filename, e))
