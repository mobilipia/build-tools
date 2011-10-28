'Project-wide default values'
from os import path

FORGE_ROOT = path.abspath(path.join(__file__, "..", ".."))
CONFIG_FILE = path.join(FORGE_ROOT, 'webmynd_build.json')
PASSWORD = "your password"

SRC_DIR = 'src'
APP_CONFIG_FILE = path.join(SRC_DIR, 'config.json')
TEMPLATE_DIR = '.template'
INSTRUCTIONS_DIR = path.join(TEMPLATE_DIR, 'generate_dynamic')