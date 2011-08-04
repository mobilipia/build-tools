import argparse
import logging
import os
from os import path
import re
import shutil
import tarfile
import tempfile
import zipfile

from nose.tools import raises, assert_raises_regexp, assert_equals, assert_not_equals, assert_true

import wm_dev_env
from wm_dev_env import DirectorySync, BuildConfig

def setup(self):
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    wm_dev_env.add_general_options(parser)
    args = parser.parse_args(['-v'])
    wm_dev_env.setup_logging(args)