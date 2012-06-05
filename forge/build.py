import logging
import os
from os import path
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
		"web": "web",
		"wp": "wp"
	}
	
	enabled_platforms = []
	if not path.isdir(build_type_dir):
		LOG.debug("no output directory {dir} found: has any build been run yet?".format(
			dir=build_type_dir
		))
		return []

	for directory in os.listdir(build_type_dir):
		if directory in directory_to_platform:
			enabled_platforms.append(directory_to_platform[directory])
		else:
			LOG.debug("ignoring non-target directory {0}".format(directory))
	return enabled_platforms

def import_generate_dynamic(do_reload=False):
	"""Load the dynamically-fetched generate libs.

	:param do_reload: refresh a potentially changed module?
	"""
	try:
		import generate_dynamic
		if do_reload:
			# need to do build and lib first so we can use @task
			reload(sys.modules['generate_dynamic.build'])
			reload(sys.modules['generate_dynamic.lib'])
			# ... and not reload them twice
			for name, module in sys.modules.items():
				if module and \
						name.startswith('generate_dynamic') and \
						name != 'generate_dynamic.build' and \
						name != 'generate_dynamic.lib':
					reload(module)
	except ImportError:
		sys.path.insert(0, path.abspath('.template'))
		sys.path.insert(0, path.abspath(path.join('.template', 'lib')))
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

def create_build(build_type_dir, targets=None, extra_args=None):
	'''Helper to instantiate a Build object from the dynamic generate code
	
	Assumes the working directory is alongside src and development
	
	:param build_type_dir: currently always "development"
	:param targets: the targets this build will concern itself with;
		a value of `None` signifies all targets
	:type targets: iterable
	:param extra_args: command line arguments that haven't been consumed yet
	:type extra_args: sequence
	'''
	generate_dynamic = import_generate_dynamic()
	app_config = build_config.load_app()
	local_config = build_config.load_local()
	extra_args = [] if extra_args is None else extra_args
	ignore_patterns = _get_ignore_patterns_for_src(defaults.SRC_DIR)
	enabled_platforms = _enabled_platforms(build_type_dir)
	if targets is not None:
		enabled_platforms = set(enabled_platforms) & set(targets)
	
	build_to_run = generate_dynamic.build.Build(app_config, defaults.SRC_DIR,
		build_type_dir, enabled_platforms=enabled_platforms, ignore_patterns=ignore_patterns,
		local_config=local_config, extra_args=extra_args, forge_root=defaults.FORGE_ROOT)
	
	return build_to_run
