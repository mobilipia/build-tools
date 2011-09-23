import codecs
import json
import logging
from os import path

import webmynd
from webmynd import defaults

LOG = logging.getLogger(__name__)

def load(filename=None):
	'Read in and JSON the app-indendent configuration file (normally webmynd_build.json)'
	if filename is None:
		filename = defaults.CONFIG_FILE
	
	with open(filename) as conf_file:
		config = json.load(conf_file)
	
	if path.exists(defaults.APP_CONFIG_FILE):
		config['uuid'] = load_app(defaults.APP_CONFIG_FILE)['uuid']
	
	LOG.debug('WebMynd build tools version: %s' % webmynd.VERSION)
	for key, val in config.iteritems():
		LOG.debug('%s: %s' % (key, json.dumps(val)))
	
	return config

def load_app(filename=None):
	'Read in and JSON parse the per-app configuration file (normall user/config.json)'
	if filename is None:
		filename = defaults.APP_CONFIG_FILE
	
	with codecs.open(filename, encoding='utf8') as app_config:
		return json.load(app_config)