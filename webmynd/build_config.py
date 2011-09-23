import json
import logging
from os import path

import webmynd
from webmynd import defaults

LOG = logging.getLogger(__name__)

def load(filename=None):
	if filename is None:
		filename = defaults.CONFIG_FILE
	
	with open(filename) as conf_file:
		config = json.load(conf_file)
	
	if path.exists(defaults.APP_CONFIG_FILE):
		with open(defaults.APP_CONFIG_FILE) as app_conf_file:
			config['uuid'] = json.load(app_conf_file)['uuid']
	
	LOG.debug('WebMynd build tools version: %s' % webmynd.VERSION)
	for key, val in config.iteritems():
		LOG.debug('%s: %s' % (key, json.dumps(val)))
	
	return config