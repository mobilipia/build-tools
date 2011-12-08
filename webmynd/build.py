import logging
import os
import sys

from webmynd import build_config, defaults, ForgeError

LOG = logging.getLogger(__name__)

def _enabled_platforms(build_type_dir):
	'''Return a list of the platforms enabled for this app
	
	Assumes the working directory is alongside src and {development,production}
	
	:param build_type_dir: development or production
	'''

	directory_to_platform = {
		"chrome": "chrome",
		"firefox": "firefox",
		"ie": "ie",
		"webmynd.safariextension": "safari",
		"android": "android",
		"ios": "ios",
	}
	
	enabled_platforms = []
	for directory in os.listdir(build_type_dir):
		if directory in directory_to_platform:
			enabled_platforms.append(directory_to_platform[directory])
		else:
			LOG.debug("ignoring non-target directory {}".format(directory))
	return enabled_platforms

def import_generate_dynamic():
	try:
		import generate_dynamic
	except ImportError:
		sys.path.insert(0, '.template')
		try:
			import generate_dynamic
		except ImportError as e:
			raise ForgeError("Couldn't import generation code: {}".format(e))
	
	return generate_dynamic

def create_build(build_type_dir):
	'''Helper to instantiate a Build object from the dynamic generate code
	
	Assumes the working directory is alongside src and {development,production}
	
	:param build_type_dir: development or production
	'''
	generate_dynamic = import_generate_dynamic()
	app_config = build_config.load_app(defaults.APP_CONFIG_FILE)
	
	build_to_run = generate_dynamic.build.Build(app_config, defaults.SRC_DIR,
		build_type_dir, enabled_platforms=_enabled_platforms(build_type_dir))
	
	return build_to_run