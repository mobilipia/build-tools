import codecs
from contextlib import contextmanager
import logging
import subprocess
import zipfile
import sys
import os
from os.path import join, isdir, islink
from os import error, listdir
import os
import time

LOG = logging.getLogger(__file__)

def path_to_data_file(*relative_path):
	'''This is a helper function that will return the path to a data file bundled inside the application.

	It is aware of whether the application is frozen (e.g. being run from forge.exe) or not.

	http://www.pyinstaller.org/export/latest/trunk/doc/Manual.html#adapting-to-being-frozen
	'''
	return os.path.join(forge.DATA_PATH, *relative_path)

def path_to_config_file(*relative_path):
	if sys.platform.startswith("win"):
		return os.path.join(
			os.environ['LOCALAPPDATA'],
			'forge',
			*relative_path
		)
	elif sys.platform.startswith("darwin"):
		return os.path.join(
			os.path.expanduser('~'),
			'.forge'
		)
	elif sys.platform.startswith("linux"):
		return os.path.join(
			os.path.expanduser('~'),
			'.forge'
		)

def try_a_few_times(f):
	try_again = 0
	while try_again < 5:
		time.sleep(try_again)
		try:
			try_again += 1
			f()
			break
		except:
			if try_again == 5:
				raise

@contextmanager
def cd(target_dir):
	'Change directory to :param:`target_dir` as a context manager - i.e. rip off Fabric'
	old_dir = os.getcwd()
	try:
		os.chdir(target_dir)
		yield target_dir
	finally:
		os.chdir(old_dir)

@contextmanager
def open_file(*args, **kw):
	'Simple wrapper around codecs.open for easier testing/mocking'
	if 'encoding' not in kw:
		kw['encoding'] = 'utf8'
	yield codecs.open(*args, **kw)

def human_readable_file_size(file):
	'Takes a python file object and gives back a human readable file size'
	size = os.fstat(file.fileno()).st_size
	return format_size_in_bytes(size)

def extract_zipfile(zip):
	'''Extracts all the contents of a zipfile.

	Use this instead of zipfile.extractall which is broken for very early python 2.6
	'''
	for f in sorted(zip.namelist()):
		if f.endswith('/'):
			os.makedirs(f)
		else:
			zip.extract(f)

def format_size_in_bytes(size_in_bytes):
	for x in ['bytes','KB','MB','GB','TB']:
		if size_in_bytes < 1024.0:
			return "%3.1f%s" % (size_in_bytes, x)
		size_in_bytes /= 1024.0

def unzip_with_permissions(filename):
	'''Helper function which attempts to use the 'unzip' program if it's installed on the system.

	This is because a ZipFile doesn't understand unix permissions (which aren't really in the zip spec),
	and strips them when it has its contents extracted.
	'''

	try:
		subprocess.Popen(["unzip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	except OSError:
		LOG.debug("'unzip' not available, falling back on python ZipFile, this will strip certain permissions from files")
		zip_to_extract = zipfile.ZipFile(filename)
		extract_zipfile(zip_to_extract)
		zip_to_extract.close()
	else:
		LOG.debug("unzip is available, using it")
		zip_process = subprocess.Popen(["unzip", filename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		output = zip_process.communicate()[0]
		LOG.debug("unzip output")
		LOG.debug(output)
