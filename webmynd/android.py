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

def runShell(args):
	proc = Popen(args, stdout=PIPE, stderr=STDOUT)
	proc_std = proc.communicate()[0]
	if proc.returncode != 0:
		raise Exception('failed: %s' % (proc_std))
	LOG.debug('Output:\n'+proc_std)

def runAndroid(sdk, jdk, device):
	LOG.info('Creating Android .apk file')
	os.chdir(os.path.join('development', 'android'))

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
	args = [sdk+'platform-tools/adb', 'devices']
	proc = Popen(args, stdout=PIPE)
	proc_std = proc.communicate()[0]
	if proc.returncode != 0:
		raise Exception('failed: %s' % (proc_std))
	lines = proc_std.split('\n')
	chosenDevice = ''
	for line in lines:
		words = line.split('\t')
		if len(words[0]) > 5 and words[0].find(" ") == -1:
			if chosenDevice == '' or words[0] == device:
				chosenDevice = words[0]
			LOG.info('Available Android device: %s' % words[0])
	LOG.info('Using Android device: %s' % chosenDevice)
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
	