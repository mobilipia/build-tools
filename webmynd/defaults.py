'Project-wide default values'
from os import path

FORGE_ROOT = path.abspath(path.join(__file__, "..", ".."))
CONFIG_FILE = path.join(FORGE_ROOT, 'webmynd_build.json')
PASSWORD = "your password"

USER_DIR = 'user'
APP_CONFIG_FILE = path.join(USER_DIR, 'config.json')
