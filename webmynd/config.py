'''Convenience classes for dealing with dictionary-based configuration'''
from copy import deepcopy
import json
import logging
from os import path

import webmynd
from webmynd import defaults

LOG = logging.getLogger(__name__)

__all__ = ['BuildConfig']

class BuildConfig(object):
	'Parses a JSON-encoded build configuration and offers convenient lookup'
	
	DUMMY_CONFIG = {
		"authentication": {
			"username": "your user name",
			"password": "your secret"
		},
		"main": {
			"uuid": "TEST-UUID",
			"server": "http://test.webmynd.com/api/"
		}
	}

	def parse(self, config_file):
		'''Read and parse a JSON build configuration file
		
		:param config_file: name of the file to read in
		:raises Exception: if the named file doesn't exist
		'''
		super(BuildConfig, self).__init__()

		if not path.isfile(config_file):
			if config_file == defaults.CONFIG_FILE:
				msg = "Didn't find default configuration file \"%s\"" % config_file
			else:
				msg = 'Configuration file "%s" does not exist' % config_file
			raise Exception(msg)
			
		with open(config_file) as config_file_:
			self._config = json.load(config_file_)
		
		LOG.debug('WebMynd build tools version %s' % webmynd.VERSION)
		public_conf = deepcopy(self._config)
		public_conf['authentication']['password'] = 'xxxxxxxx'
		for key, val in public_conf.iteritems():
			LOG.debug('%s: %s' % (key, json.dumps(val)))
			
	def get(self, keys, default='__ nonsensical default'):
		'''Lookup a configuration value.
		
		For example, if we'd previously parsed a file with::
		
			{"section": {"subsection": {"key": "value"}}}
			
		as its contents::
		
			>>> build_config.get('section.subsection.key')
			'value'
			>>> build_config.get('section.subsection.not_here', default='default val')
			'default val'
		
		:param keys: dot-separated key names to drill into configuration
		:param default: value to return if the specified configuration is not found
		:return: requested configuration value, or the default if not found
		:raises KeyError: if no default is given, and the requested configuration
			value isn't found
		'''
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
		'Internal use only: an exemplar instance with dummy contents'
		res = BuildConfig()
		res._config = cls.DUMMY_CONFIG
		return res