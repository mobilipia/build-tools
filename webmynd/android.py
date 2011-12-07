from collections import namedtuple
import codecs
import json
import logging
import os
from os import path
import re
import shutil
from subprocess import Popen, PIPE, STDOUT
import sys
import tempfile
import time
import urllib
import zipfile

from webmynd import build, ForgeError

LOG = logging.getLogger(__name__)

def run_android(build_type_dir, sdk, device):
	
	build_to_run = build.create_build(build_type_dir)

	build_to_run.add_steps(customer_phases.run_android_phase(sdk, device))
	
	try:
		build_to_run.run()
	except Exception as e:
		raise ForgeError(e)