import json

from webmynd import defaults

def load(filename=None):
	if filename is None:
		filename = defaults.CONFIG_FILE
	
	with open(filename) as conf_file:
		return json.load(conf_file)