import collections
import codecs
from contextlib import contextmanager
import logging
import subprocess
import zipfile
import sys
import os
from os import path
import time
import urlparse
import threading

from forge import defaults

LOG = logging.getLogger(__file__)


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

def extract_zipfile(zip, out_path="."):
	'''Extracts all the contents of a zipfile.

	Use this instead of zipfile.extractall which is broken for very early python 2.6
	'''
	for f in sorted(zip.namelist()):
		if f.endswith('/'):
			os.makedirs(os.path.join(out_path,f))
		else:
			zip.extract(f, path=out_path)

def format_size_in_bytes(size_in_bytes):
	for x in ['bytes','KB','MB','GB','TB']:
		if size_in_bytes < 1024.0:
			return "%3.1f%s" % (size_in_bytes, x)
		size_in_bytes /= 1024.0

def unzip_with_permissions(filename, out_path="."):
	'''Helper function which attempts to use the 'unzip' program if it's installed on the system.

	This is because a ZipFile doesn't understand unix permissions (which aren't really in the zip spec),
	and strips them when it has its contents extracted.
	'''
	LOG.debug('Unzipping {zip} to {dest}'.format(zip=filename, dest=out_path))
	try:
		PopenWithoutNewConsole(["unzip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	except OSError:
		LOG.debug("'unzip' not available, falling back on python ZipFile, this will strip certain permissions from files")
		zip_to_extract = zipfile.ZipFile(filename)
		extract_zipfile(zip_to_extract, out_path)
		zip_to_extract.close()
	else:
		LOG.debug("unzip is available, using it")
		zip_process = PopenWithoutNewConsole(["unzip", "-o", filename, "-d", out_path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
		output = zip_process.communicate()[0]
		LOG.debug("unzip output")
		LOG.debug(output)


class AccidentHandler(logging.Handler):
	def __init__(self, capacity, flush_level, target):
		logging.Handler.__init__(self)
		self.records = collections.deque(maxlen=capacity)
		self.capacity = capacity
		if isinstance(flush_level, str):
			self.flush_level = getattr(logging, flush_level)
		else:
			self.flush_level = flush_level
		self.target = target
		self.should_flush = False

	def flush(self):
		if self.should_flush:
			for rec in self.records:
				self.target.emit(rec)
			self.records.clear()
			self.target.flush()

	def emit(self, record):
		if record.levelno >= self.flush_level:
			self.should_flush = True

		self.records.append(record)

def platform_changeset(app_path="."):
	"""
	Return the changeset of the platform used to build the current template.

	Assumes the existence of ``changeset.txt`` in the lib directory of .template.
	"""
	changeset_file = path.join(app_path, defaults.TEMPLATE_DIR, "lib", "changeset.txt")
	if path.isfile(changeset_file):
		with open(changeset_file) as changeset_f:
			return changeset_f.read().strip()
	else:
		return ""

class RequestWrapper(object):
	def __init__(self, request):
		self._request = request
		self.unverifiable = False

	def get_full_url(self):
		return self._request.full_url

	def get_host(self):
		return urlparse.urlparse(self._request.full_url).hostname

	def get_origin_req_host(self):
		# TODO: find out and document what this actually means
		# check RFC 2965
		return self.get_host()

	def is_unverifiable(self):
		return self.unverifiable

class ResponseWrapper(object):
	def __init__(self, response):
		self._response = response

	def info(self):
		return self._response.raw._fp.msg

def load_cookies_from_response(response, jar):
	"""Takes a requests.models.Response object and loads any cookies set in it
	into the given cookielib.CookieJar
	"""
	req = RequestWrapper(response.request)
	resp = ResponseWrapper(response)
	jar.extract_cookies(resp, req)

# TODO: this is duplicated in generate module, we should figure out a way to share
# the code between generate_dynamic and build tools sensibly
class PopenWithoutNewConsole(subprocess.Popen):
	"""Wrapper around Popen that adds the appropriate options to prevent launching
	a new console window everytime we want to launch a subprocess.
	"""
	_old_popen = subprocess.Popen

	def __init__(self, *args, **kwargs):
		if sys.platform.startswith("win") and 'startupinfo' not in kwargs:
			startupinfo = subprocess.STARTUPINFO()
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = subprocess.SW_HIDE
			kwargs['startupinfo'] = startupinfo

		self._old_popen.__init__(self, *args, **kwargs)


class FilterHandler(logging.Handler):
	def __init__(self, target_handler, filter, *args, **kwargs):
		logging.Handler.__init__(self, *args, **kwargs)
		self._filter = filter
		self._target_handler = target_handler

	def emit(self, record):
		# if the record originated in the desired thread,
		# let it through to the target
		if self._filter(record):
			self._target_handler.emit(record)


class CurrentThreadHandler(logging.Handler):
	"""Wraps another logging.Handler and forwards on records to it if they originated from
	a particular thread.

	Used to distinguish between output from the main build tools thread	and the task thread.
	"""
	def __init__(self, target_handler, *args, **kwargs):
		logging.Handler.__init__(self, *args, **kwargs)
		self._target_handler = target_handler
		# Thread.name more reliable than Thread.ident:
		# http://bugs.python.org/issue5632
		self._thread_name = threading.current_thread().name

	def emit(self, record):
		# if the record originated in the desired thread,
		# let it through to the target
		if record.threadName == self._thread_name:
			self._target_handler.emit(record)


class ProgressBar(object):
	"""Helper context manager to emit progress events. e.g.

	with ProgressBar('Downloading Android SDK'):
		time.sleep('2')
		bar.progress(0.25) # 25% complete
		time.sleep('2')
		bar.progress(0.5) # 50% complete

	# 100% complete if finishes without exception

	*N.B* any logging occuring during the progress bar will mess up
	how it looks in the commandline, might be able to resolve this later
	by erasing the progress bar, printing the log output then printing the progress bar.
	"""
	def __init__(self, message):
		self._message = message
		from forge import async
		self._call = async.current_call()

	def __enter__(self):
		self._call.emit('progressStart', message=self._message)
		return self

	def progress(self, fraction):
		self._call.emit('progress', fraction=fraction, message=self._message)

	def __exit__(self, exc_type, exc_val, exc_tb):
		if exc_type is not None:
			self.progress(1)
		self._call.emit('progressEnd', message=self._message)


def set_file_as_hidden(to_hide):
	if sys.platform == 'win32':
		try:
			PopenWithoutNewConsole(['attrib', '+h', to_hide], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()
		except Exception as e:
			import traceback
			LOG.debug("Failed to mark %s as hidden: %s" % (to_hide, e))
			LOG.debug(traceback.format_exc(e))


#TODO: some versions should be marked as old and minor?
def classify_platform(stable_version, current_version):
	"""Classifies a platform version as:

	'nonstandard', 'minor', 'old' or None if it's up to date.
	"""
	stable_version = stable_version.split('.')
	current_version = current_version.split('.')
	
	if not current_version[0].startswith('v'):
		return 'nonstandard'

	try:
		without_v = [current_version[0][1:]] + current_version[1:]
		map(int, without_v)
	except ValueError:
		return 'nonstandard'

	if len(current_version) > 2:
		return 'minor'

	if int(current_version[0][1:]) < int(stable_version[0][1:]) or (int(current_version[0][1:]) == int(stable_version[0][1:]) and int(current_version[1]) < int(stable_version[1])):
		return 'old'
