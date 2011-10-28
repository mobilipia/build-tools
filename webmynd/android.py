import os
from os import path
import zipfile
import codecs
import json
import re
import logging
import sys
import tempfile
import shutil
import urllib
import time
from subprocess import Popen, PIPE, STDOUT

from webmynd import defaults, ForgeError

LOG = logging.getLogger(__name__)

class CouldNotLocate(Exception):
	pass

def check_for_android_sdk(dir):
	# Some sensible places to look for the Android SDK
	possibleSdk = [
		"C:/Program Files (x86)/Android/android-sdk/",
		"C:/Program Files/Android/android-sdk/",
		"C:/Android/android-sdk/",
		"C:/Android/android-sdk-windows/",
		"C:/android-sdk-windows/",
		"/Applications/android-sdk-macosx"
	]
	if dir:
		possibleSdk.insert(0, dir)

	for directory in possibleSdk:
		if os.path.isdir(directory):
			if directory.endswith('/'):
				return directory
			else:
				return directory+'/'
	else:
		# No SDK found - will the user let us install one?
		path = None
		
		if sys.platform.startswith('win'):
			path = "C:\\android-sdk-windows"
		#elif sys.platform.startswith('linux'):
		#	path = "/opt/android-sdk-linux"
		elif sys.platform.startswith('darwin'):
			path = "/Applications/android-sdk-macosx"
			
		if not path:
			raise CouldNotLocate("No Android SDK found, please specify with the --sdk flag")		
		
		prompt = raw_input('\nNo Android SDK found, would you like to:\n(1) Attempt to download and install the SDK automatically to '+path+', or,\n(2) Install the SDK yourself and rerun this command with the --sdk option to specify its location.\nPlease enter 1 or 2: ')
		
		if not prompt == "1":
			raise CouldNotLocate("No Android SDK found, please specify with the --sdk flag")
		else:
			# Attempt download
			orig_dir = os.getcwd()
			temp_d = tempfile.mkdtemp()
			try:
				os.chdir(temp_d)
				LOG.info('Downloading Android SDK (about 30MB, may take some time)')
				
				if sys.platform.startswith('win'):
					urllib.urlretrieve("http://dl.google.com/android/android-sdk_r14-windows.zip", "sdk.zip")

					LOG.info('Download complete, extracting SDK')
					zip_to_extract = zipfile.ZipFile("sdk.zip")
					zip_to_extract.extractall("C:\\")
					zip_to_extract.close()
					
					android_path = "C:\\android-sdk-windows\\tools\\android.bat"
					adb_path = "C:\\android-sdk-windows\\platform-tools\\adb"
				elif sys.platform.startswith('darwin'):
					urllib.urlretrieve("http://dl.google.com/android/android-sdk_r14-macosx.zip", "sdk.zip")
	
					LOG.info('Download complete, extracting SDK')
					zip_process = Popen(["unzip", "sdk.zip", '-d', "/Applications"], stdout=PIPE, stderr=STDOUT)
					output = zip_process.communicate()[0]
					LOG.debug("unzip output")
					LOG.debug(output)
					
					android_path = "/Applications/android-sdk-macosx/tools/android"
					adb_path = "/Applications/android-sdk-macosx/platform-tools/adb"
					
				LOG.info('Extracted, updating SDK and downloading required Android platform (about 90MB, may take some time)')
				android_process = Popen([android_path, "update", "sdk", "--no-ui", "--filter", "platform-tool,tool,android-8"], stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
				while android_process.poll() == None:
					time.sleep(5)
					try:
						Popen([adb_path, "kill-server"], stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w'))
					except:
						pass

				LOG.info('Android SDK update complete')
				return check_for_android_sdk(None)
			finally:
				os.chdir(orig_dir)
				shutil.rmtree(temp_d, ignore_errors=True)

			raise CouldNotLocate("Automatic SDK download failed, please install manually and specify with the --sdk flag")

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
	return proc_std

def runBackground(args, detach=False):
	if sys.platform.startswith('win'):
		# Windows only
		DETACHED_PROCESS = 0x00000008
		Popen(args, creationflags=DETACHED_PROCESS)
	else:
		if detach:
			os.system("osascript -e 'tell application \"Terminal\" to do script \""+" ".join(args)+"\"'")
		else:
			os.system(" ".join(args)+" &")

def runAndroid(sdk, device):
	LOG.info('Looking for Android device')
	orig_dir = os.getcwd()
	os.chdir(os.path.join('development', 'android'))
	
	adb_location = path.abspath(path.join(sdk,'platform-tools','adb'))
	if sys.platform.startswith('win'):
		android_path = path.abspath(path.join(sdk,'tools','android.bat'))
	else:
		android_path = path.abspath(path.join(sdk,'tools','android'))

	runBackground([adb_location, 'start-server'])
	time.sleep(1)
	
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
		# Prompt to automatically (create and) run an AVD
		prompt = raw_input('\nNo active Android device found, would you like to:\n(1) Attempt to automatically launch the Android emulator\n(2) Attempt to find the device again (choose this option after plugging in an Android device or launching the emulator).\nPlease enter 1 or 2: ')
		if not prompt == "1":
			os.chdir(orig_dir)
			return runAndroid(sdk, device)
		else:
			pass

		# Create avd
		if os.path.isdir(os.path.join(sdk, 'forge-avd')):
			LOG.info('Existing AVD found')
		else:
			LOG.info('Creating AVD')
			args = [
				android_path,
				"create",
				"avd",
				"-n", "forge",
				"-t", "android-8",
				"--skin", "HVGA",
				"-p", os.path.join(sdk, 'forge-avd'),
				#"-a",
				"-c", "32M"
			]
			proc = Popen(args, stdin=PIPE, stdout=PIPE, stderr=STDOUT)
			time.sleep(0.1)
			proc_std = proc.communicate(input='\n')[0]
			if proc.returncode != 0:
				LOG.error('failed: %s' % (proc_std))
				raise ForgeError
			LOG.debug('Output:\n'+proc_std)

		# Launch
		runBackground([os.path.join(sdk, "tools", "emulator"), "-avd", "forge"], detach=True)
		
		LOG.info("Started emulator, waiting for device to boot")
		args = [
			adb_location,
			"wait-for-device"
		]
		runShell(args)
		args = [
			adb_location,
			"shell", "pm", "path", "android"
		]
		output = "Error:"
		while output.startswith("Error:"):
			output = runShell(args)
		os.chdir(orig_dir)
		return runAndroid(sdk, device)

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
	
	LOG.info('Creating Android .apk file')
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
		'java',
		'-jar',
		os.path.join(defaults.FORGE_ROOT, 'webmynd', 'apk-signer.jar'),
		'--keystore',
		os.path.join(defaults.FORGE_ROOT, 'debug.keystore'),
		'--storepass',
		'android',
		'--keyalias',
		'androiddebugkey',
		'--keypass',
		'android',
		'--out',
		'signed-app.apk',
		'app.apk'
	]
	runShell(args)

	#align
	LOG.info('Aligning apk')
	if os.path.exists('out.apk'):
		os.remove('out.apk')
	args = [sdk+'tools/zipalign', '-v', '4', 'signed-app.apk', 'out.apk']
	runShell(args)
	os.remove('app.apk')
	os.remove('signed-app.apk')

	#install
	LOG.info('Installing apk')
	args = [sdk+'platform-tools/adb', '-s', chosenDevice, 'install', '-r', 'out.apk']
	runShell(args) 

	#run
	LOG.info('Running apk')
	# Get the app config details
	with codecs.open(os.path.join('..', '..', 'src', 'config.json'), encoding='utf8') as app_config:
		app_config = json.load(app_config)
	package_name = re.sub("[^a-zA-Z0-9]", "", app_config["name"].lower())+app_config["uuid"];
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