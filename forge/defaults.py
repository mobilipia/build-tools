'Project-wide default values'
import sys
from os import path
import os

# if we're running the packaged forge.exe
if 'frozen' in set(dir(sys)):
	# then look for config file relative to forge.exe
	FORGE_ROOT = path.dirname(sys.executable)

# else we're running from the non-packaged version (i.e. during development)
else:
	# so look for config file relative to the unpackaged library files
	FORGE_ROOT = path.abspath(path.join(__file__, "..", ".."))


CONFIG_FILE = path.join(FORGE_ROOT, 'forge_build.json')
PASSWORD = "your password"

SRC_DIR = 'src'
APP_CONFIG_FILE = path.join(SRC_DIR, 'config.json')
IDENTITY_FILE = path.join(SRC_DIR, 'identity.json')
TEMPLATE_DIR = '.template'
INSTRUCTIONS_DIR = path.join(TEMPLATE_DIR, 'generate_dynamic')