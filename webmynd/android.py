import os
from os import path
import zipfile
import codecs
import json
import re
import logging
import sys
from subprocess import Popen, PIPE, STDOUT

from webmynd import defaults, ForgeError

LOG = logging.getLogger(__name__)

def scrape_available_devices(text):
	'Scrapes the output of the adb devices command into a list'
	lines = text.split('\n')
	available_devices = []

	for line in lines:
		words = line.split('\t')

		if len(words[0]) > 5 and words[0].find(" ") == -1:
			available_devices.append(words[0])

	return available_devices

def runShell(args):
	proc = Popen(args, stdout=PIPE, stderr=STDOUT)
	proc_std = proc.communicate()[0]
	if proc.returncode != 0:
		LOG.error('failed: %s' % (proc_std))
		raise ForgeError
	LOG.debug('Output:\n'+proc_std)

def runAndroid(sdk, jdk, device):
	LOG.info('Creating Android .apk file')
	os.chdir(os.path.join('development', 'android'))
	
	proc = Popen([path.abspath(path.join(sdk,'platform-tools','adb')), 'start-server'], stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
	
	#zip
	LOG.info('Zipping files')
	zipf = zipfile.ZipFile('app.apk', mode='w')
	for root, _, files in os.walk('.'):
		if root == '.':
			root = ''
		else: 
			root = root.replace('\\', '/')+"/"
			if root[0:2] == './':
				root = root[2:]
		for f in files:
			if f != 'app.apk':
				LOG.debug('zipping: %s' % f)
				zipf.write(root+f, root+f)
	zipf.close()

	#sign
	LOG.info('Signing apk')
	args = [
		jdk+'jarsigner',
		'-verbose',
		'-keystore',
		os.path.join(defaults.FORGE_ROOT, 'debug.keystore'),
		'-storepass',
		'android',
		'app.apk',
		'androiddebugkey',
		'-keypass',
		'android'
	]
	runShell(args)

	#align
	LOG.info('Aligning apk')
	if os.path.exists('out.apk'):
		os.remove('out.apk')
	args = [sdk+'tools/zipalign', '-v', '4', 'app.apk', 'out.apk']
	runShell(args)
	os.remove('app.apk')

	# TODO choose device
	adb_location = path.abspath(path.join(sdk,'platform-tools','adb'))
	args = [adb_location, 'devices']
	try:
		proc = Popen(args, stdout=PIPE)
	except Exception as e:
		LOG.error("problem finding the android debug bridge at: %s" % adb_location)
		# XXX: prompt to run the sdk manager, then retry?
		LOG.error("this probably means you need to run the android SDK manager and download the android platform-tools.")
		raise ForgeError

	proc_std = proc.communicate()[0]
	if proc.returncode != 0:
		LOG.error('Communication with adb failed: %s' % (proc_std))
		raise ForgeError

	available_devices = scrape_available_devices(proc_std)

	if not available_devices:
		LOG.error('There were no attached android devices')
		# XXX: prompt to run the sdk manager, then retry?
		LOG.error('you need to run the android SDK manager and start a virtual android device, or attach a physical android device to the adb')
		raise ForgeError

	if not device:
		chosenDevice = available_devices[0]
		LOG.info('No android device specified, defaulting to %s' % chosenDevice)

	elif device:

		if device in available_devices:
			chosenDevice = device
			LOG.info('Using specified android device %s' % chosenDevice)
		else:
			LOG.error('No such device "%s"' % device)
			LOG.error('The available devices are:')
			LOG.error("\n".join(available_devices))
			raise ForgeError

	#install
	LOG.info('Installing apk')
	args = [sdk+'platform-tools/adb', '-s', chosenDevice, 'install', '-r', 'out.apk']
	runShell(args) 

	#run
	LOG.info('Running apk')
	# Get the app config details
	with codecs.open(os.path.join('assets','config.json'), encoding='utf8') as app_config:
		app_config = json.load(app_config)
	package_name = re.sub("[^a-zA-Z0-9]", "", app_config["name"].lower())+'_'+app_config["uuid"];
	args = [sdk+'platform-tools/adb', '-s', chosenDevice, 'shell', 'am', 'start', '-n', 'webmynd.generated.'+package_name+'/webmynd.generated.'+package_name+'.LoadActivity']
	runShell(args)

	# TODO log output
	LOG.info('Clearing android log')
	args = [sdk+'platform-tools/adb', '-s', chosenDevice, 'logcat', '-c']
	proc = Popen(args, stdout=sys.stdout, stderr=sys.stderr)
	proc.wait()
	LOG.info('Showing android log')
	args = [sdk+'platform-tools/adb', '-s', chosenDevice, 'logcat', 'WebCore:D', package_name+':D', '*:S']
	proc = Popen(args, stdout=sys.stdout, stderr=sys.stderr)
	proc.wait()
	