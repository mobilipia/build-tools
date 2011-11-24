'Project-wide default values'
import sys
from os import path

executable_name = path.basename(sys.executable)

# this is a bit of a hack, the idea is:

# if running from the non-packaged version (i.e. during development)
if executable_name.startswith("python"):
	# then look for data files relative to the unpackaged library files
	FORGE_ROOT = path.abspath(path.join(__file__, "..", ".."))

# else we're running the packaged forge.exe
else:
	# so look for data files relative to forge.exe
	FORGE_ROOT = path.dirname(sys.executable)

CONFIG_FILE = path.join(FORGE_ROOT, 'webmynd_build.json')
PASSWORD = "your password"

SRC_DIR = 'src'
APP_CONFIG_FILE = path.join(SRC_DIR, 'config.json')
TEMPLATE_DIR = '.template'
INSTRUCTIONS_DIR = path.join(TEMPLATE_DIR, 'generate_dynamic')