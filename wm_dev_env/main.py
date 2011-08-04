import logging
import shutil

import argparse

from config import BuildConfig
import defaults
from dir_sync import DirectorySync
from generate import Generate
from remote import Remote
from templates import Manager

import wm_dev_env

log = None

def setup_logging(args):
    global log
    if args.verbose and args.quiet:
        args.error('Cannot run in quiet and verbose mode at the same time')
    if args.verbose:
        log_level = logging.DEBUG
    elif args.quiet:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO
    logging.basicConfig(level=log_level, format='[%(levelname)7s] %(asctime)s -- %(message)s')
    log = logging.getLogger(__name__)
    log.info('WebMynd tools running at version %s' % wm_dev_env.VERSION)

def add_general_options(parser):
    'Generic command-line arguments'
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    
def handle_general_options(args):
    setup_logging(args)
    
def refresh():
    'Restore consistency between customer code and whatever is in unpacked development add-ons'
    
    parser = argparse.ArgumentParser('Ensures consistency between active add-ons and your source directory')
    parser.add_argument('-c', '--config', help='a configuration file for this build', default=defaults.CONFIG_FILE)
    add_general_options(parser)
    args = parser.parse_args()
    handle_general_options(args)

    config = BuildConfig()
    config.parse(args.config)
    sync = DirectorySync(config)
    sync.user_to_target()
    
def init():
    'Create a new development environment'
    parser = argparse.ArgumentParser('Initialises your development environment')
    parser.add_argument('-c', '--config', help='a configuration file for this build', default=defaults.CONFIG_FILE)
    add_general_options(parser)
    args = parser.parse_args()
    handle_general_options(args)
    
    config = BuildConfig()
    config.parse(args.config)
    
    remote = Remote(config)
    manager = Manager(config)
    # grab user's code
    remote.get_latest_user_code(defaults.USER_DIR)
    
    # start initial template build
    build_id = int(remote.build(development=True, template_only=True))
    # retreive results of build
    manager.get_templates(build_id)
    
def development_build():
    'Pull down new version of platform code in a customised build, and create unpacked development add-on'
    
    parser = argparse.ArgumentParser('Creates new local, unzipped development add-ons with your source and configuration')
    parser.add_argument('-c', '--config', help='a configuration file for this build', default=defaults.CONFIG_FILE)
    add_general_options(parser)
    args = parser.parse_args()
    handle_general_options(args)
    
    config = BuildConfig()
    config.parse(args.config)
    remote = Remote(config)
    manager = Manager(config)

    templates_dir = manager.templates_for(remote.app_config_file)
    if templates_dir:
        log.info('configuration is unchanged: using existing templates')
    else:
        log.info('configuration has changed: creating new templates')
        # configuration has changed: new template build!
        build_id = int(remote.build(development=True, template_only=True))
        # retrieve results of build
        templates_dir = manager.get_templates(build_id)
    
    shutil.rmtree('development', ignore_errors=True)
    shutil.copytree(templates_dir, 'development')
    sync = DirectorySync(config)
    sync.user_to_target(force=True)
    generator = Generate(remote.app_config_file)
    generator.all('development', defaults.USER_DIR)

def push_code():
    'Push the customer code up to the remote server'
    pass

def production_build():
    'Trigger a new build'
    # TODO commonality between this and development_build
    parser = argparse.ArgumentParser('Start a new production build and retrieve the packaged and unpackaged output')
    parser.add_argument('-c', '--config', help='a configuration file for this build', default=defaults.CONFIG_FILE)
    add_general_options(parser)
    args = parser.parse_args()
    handle_general_options(args)

    config = BuildConfig()
    config.parse(args.config)
    remote = Remote(config)
    sync = DirectorySync(config)
    
    build_id = int(remote.build(development=False, template_only=False))
    
    log.info('getting build configuration')
    remote.get_app_config(build_id)

    log.info('fetching new WebMynd build')
    remote.fetch_unpackaged(build_id, to_dir='production')

