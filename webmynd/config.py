from copy import deepcopy
import json
import logging
from os import path

import webmynd

log = logging.getLogger(__name__)

class BuildConfig(object):
	DUMMY_CONFIG = {
		"authentication": {
			"username": "your user name",
			"password": "your secret"
		},
		"main": {
			"uuid": "DEAD-BEEF",
			"server": "http://test.webmynd.com/api/"
		}
	}

	def parse(self, config_file):
		super(BuildConfig, self).__init__()

		if not path.isfile(config_file):
			if config_file == webmynd.defaults.CONFIG_FILE:
				msg = "Didn't find default configuration file \"%s\"" % config_file
			else:
				msg = 'Configuration file "%s" does not exist' % config_file
			raise Exception(msg)
			
		with open(config_file) as config_file_:
			self._config = json.load(config_file_)

		
		log.debug('WebMynd development tools version %s' % webmynd.VERSION)
		public_conf = deepcopy(self._config)
		public_conf['authentication']['password'] = 'xxxxxxxx'
		for key, val in public_conf.iteritems():
			log.debug('%s: %s' % (key, json.dumps(val)))
			
	def get(self, keys, default='__ nonsensical default'):
		current = self._config
		for key in keys.split('.'):
			try:
				current = current[key]
			except KeyError:
				if default == '__ nonsensical default':
					raise
				else:
					return default
		return current
	
	@classmethod
	def _test_instance(cls):
		res = BuildConfig()
		res._config = cls.DUMMY_CONFIG
		return res