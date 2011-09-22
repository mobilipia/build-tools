'Entry points for the WebMynd build tools'
import logging
import shutil

import argparse
import os
import time
import zipfile
import codecs
import json
import re
from subprocess import Popen, PIPE

import webmynd
from webmynd.config import Config
from webmynd import defaults
from webmynd.generate import Generate
from webmynd.remote import Remote
from webmynd.templates import Manager

LOG = None

def setup_logging(args):
	'Adjust logging parameters according to command line switches'
	global LOG
	if args.verbose and args.quiet:
		args.error('Cannot run in quiet and verbose mode at the same time')
	if args.verbose:
		log_level = logging.DEBUG
	elif args.quiet:
		log_level = logging.WARNING
	else:
		log_level = logging.INFO
	logging.basicConfig(level=log_level, format='[%(levelname)7s] %(asctime)s -- %(message)s')
	LOG = logging.getLogger(__name__)
	LOG.info('WebMynd tools running at version %s' % webmynd.VERSION)

def add_general_options(parser):
	'Generic command-line arguments'
	parser.add_argument('-v', '--verbose', action='store_true')
	parser.add_argument('-q', '--quiet', action='store_true')
	
def handle_general_options(args):
	'Parameterise our option based on common command-line arguments'
	setup_logging(args)

def run():
	parser = argparse.ArgumentParser('Run a built dev app on a particular platform')
	parser.add_argument('platform', choices=['android'])
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	if args.platform == 'android':
		jdk = 'C:/Program Files/Java/jdk1.6.0_26/bin/'
		sdk = 'C:/android-sdk-windows/'
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
		args = [jdk+'jarsigner', '-verbose', '-keystore', '../../debug.keystore', '-storepass', 'android', 'app.apk', 'androiddebugkey', '-keypass', 'android']
		proc = Popen(args, stdout=PIPE, stderr=PIPE)
		proc_std = proc.communicate()
		if proc.returncode != 0:
			raise Exception('failed: %s' % (proc_std[1]))
		LOG.debug('\n'+proc_std[0])
		LOG.debug('\n'+proc_std[1])
		#align
		LOG.info('Aligning apk')
		os.remove('out.apk')
		args = [sdk+'tools/zipalign', '-v', '4', 'app.apk', 'out.apk']
		proc = Popen(args, stdout=PIPE, stderr=PIPE)
		proc_std = proc.communicate()
		if proc.returncode != 0:
			raise Exception('failed: %s' % (proc_std[1]))
		LOG.debug('\n'+proc_std[0])
		LOG.debug('\n'+proc_std[1])
		os.remove('app.apk')
		# TODO choose device
		#install
		LOG.info('Installing apk')
		args = [sdk+'platform-tools/adb', 'install', '-r', 'out.apk']
		proc = Popen(args, stdout=PIPE, stderr=PIPE)
		proc_std = proc.communicate()
		if proc.returncode != 0:
			raise Exception('failed: %s' % (proc_std[1]))
		LOG.debug('\n'+proc_std[0])
		LOG.debug('\n'+proc_std[1])
		#run
		LOG.info('Running apk')
		with codecs.open(os.path.join('assets','config.json'), encoding='utf8') as app_config:
			app_config = json.load(app_config)
		package_name = re.sub("[^a-zA-Z0-9]", "", app_config["name"].lower())+'_'+app_config["uuid"];
		args = [sdk+'platform-tools/adb', 'shell', 'am', 'start', '-n', 'webmynd.generated.'+package_name+'/webmynd.generated.'+package_name+'.LoadActivity']
		print " ".join(args)
		proc = Popen(args, stdout=PIPE, stderr=PIPE)
		proc_std = proc.communicate()
		if proc.returncode != 0:
			raise Exception('failed: %s' % (proc_std[1]))
		LOG.debug('\n'+proc_std[0])
		LOG.debug('\n'+proc_std[1])
		# TODO log output
		
		
def create():
	'Create a new development environment'
	parser = argparse.ArgumentParser('Initialises your development environment')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	config = Config()
	config.parse(args.config)
	
	remote = Remote(config)
	manager = Manager(config)
	
	if os.path.exists('user'):
		LOG.info('Folder "user" already exists, if you really want to create a new app you will need to remove it!')
	else:	
		name = raw_input('Enter app name: ')
		uuid = remote.create(name)
		remote.fetch_initial(uuid)

def development_build():
	'Pull down new version of platform code in a customised build, and create unpacked development add-on'
	
	parser = argparse.ArgumentParser('Creates new local, unzipped development add-ons with your source and configuration')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)
	
	config = Config()
	config.parse(args.config)
	remote = Remote(config)
	manager = Manager(config)

	templates_dir = manager.templates_for_config(config.app_config_file)
	if templates_dir:
		LOG.info('configuration is unchanged: using existing templates')
	else:
		LOG.info('configuration has changed: creating new templates')
		# configuration has changed: new template build!
		build_id = int(remote.build(development=True, template_only=True))
		# retrieve results of build
		templates_dir = manager.fetch_templates(build_id)
	
	shutil.rmtree('development', ignore_errors=True)
	# Windows often gives a permission error without a small wait
	tryAgain = 0
	while tryAgain < 5:
		time.sleep(tryAgain)
		try:
			tryAgain = tryAgain + 10
			shutil.copytree(templates_dir, 'development')
		except Exception, e:
			tryAgain = tryAgain - 9
			if tryAgain == 5:
				raise
		
	generator = Generate(config.app_config_file)
	generator.all('development', defaults.USER_DIR)

def production_build():
	'Trigger a new build'
	# TODO commonality between this and development_build
	parser = argparse.ArgumentParser('Start a new production build and retrieve the packaged and unpackaged output')
	parser.add_argument('-c', '--config', help='your WebMynd configuration file', default=defaults.CONFIG_FILE)
	add_general_options(parser)
	args = parser.parse_args()
	handle_general_options(args)

	config = Config()
	config.parse(args.config)
	remote = Remote(config)
	
	build_id = int(remote.build(development=False, template_only=False))
	
	LOG.info('fetching new WebMynd build')
	remote.fetch_packaged(build_id, to_dir='production')