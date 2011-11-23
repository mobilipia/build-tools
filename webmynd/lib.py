from contextlib import contextmanager
import logging
import subprocess
import zipfile
import os
from os.path import join, isdir, islink
from os import error, listdir
import os
import time

LOG = logging.getLogger(__file__)

# modified os.walk() function from Python 2.4 standard library
def walk2(top, topdown=True, onerror=None, deeplevel=0): # fix 0
	"""Modified directory tree generator.

	For each directory in the directory tree rooted at top (including top
	itself, but excluding '.' and '..'), yields a 4-tuple

		dirpath, dirnames, filenames, deeplevel

	dirpath is a string, the path to the directory.  dirnames is a list of
	the names of the subdirectories in dirpath (excluding '.' and '..').
	filenames is a list of the names of the non-directory files in dirpath.
	Note that the names in the lists are just names, with no path components.
	To get a full path (which begins with top) to a file or directory in
	dirpath, do os.path.join(dirpath, name). 

	----------------------------------------------------------------------
	+ deeplevel is 0-based deep level from top directory
	----------------------------------------------------------------------
	...

	"""

	try:
		names = listdir(top)
	except error, err:
		if onerror is not None:
			onerror(err)
		return

	dirs, nondirs = [], []
	for name in names:
		if isdir(join(top, name)):
			dirs.append(name)
		else:
			nondirs.append(name)

	if topdown:
		yield top, dirs, nondirs, deeplevel # fix 1
	for name in dirs:
		path = join(top, name)
		if not islink(path):
			for x in walk2(path, topdown, onerror, deeplevel+1): # fix 2
				yield x
	if not topdown:
		yield top, dirs, nondirs, deeplevel # fix 3

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
	'Simple wrapper around __builtins__.open for easier testing/mocking'
	with open(*args, **kw) as out:
		yield out

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