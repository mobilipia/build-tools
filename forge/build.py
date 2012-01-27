import logging
import os
import sys

from forge import build_config, defaults, ForgeError, lib

LOG = logging.getLogger(__name__)

def _enabled_platforms(build_type_dir):
	'''Return a list of the platforms enabled for this app
	
	Assumes the working directory is alongside src and development
	
	:param build_type_dir: currently always "development"
	'''

	directory_to_platform = {
		"chrome": "chrome",
		"firefox": "firefox",
		"ie": "ie",
		"forge.safariextension": "safari",
		"android": "android",
		"ios": "ios",
	}
	
	enabled_platforms = []
	for directory in os.listdir(build_type_dir):
		if directory in directory_to_platform:
			enabled_platforms.append(directory_to_platform[directory])
		else:
			LOG.debug("ignoring non-target directory {0}".format(directory))
	return enabled_platforms

def import_generate_dynamic():
	try:
		import generate_dynamic
	except ImportError:
		sys.path.insert(0, '.template')
		try:
			import generate_dynamic
		except ImportError as e:
			raise ForgeError("Couldn't import generation code: {0}".format(e))
	
	return generate_dynamic

def _get_ignore_patterns_for_src(src_dir):
	"""Returns the set of match_patterns
	:param src_dir: Relative path to src directory containing user's code
	"""

	try:
		with lib.open_file(os.path.join(src_dir, '.forgeignore')) as ignore_file:
			ignores = map(lambda s: s.strip(), ignore_file.readlines())
	except Exception:
		ignores = []

	return list(set(ignores))

def create_build(build_type_dir):
	'''Helper to instantiate a Build object from the dynamic generate code
	
	Assumes the working directory is alongside src and development
	
	:param build_type_dir: currently always "development"
	'''
	generate_dynamic = import_generate_dynamic()
	app_config = build_config.load_app(defaults.APP_CONFIG_FILE)
	ignore_patterns = _get_ignore_patterns_for_src(defaults.SRC_DIR)
	
	build_to_run = generate_dynamic.build.Build(app_config, defaults.SRC_DIR,
		build_type_dir, enabled_platforms=_enabled_platforms(build_type_dir), ignore_patterns=ignore_patterns)
	
	return build_to_run
