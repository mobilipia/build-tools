from cookielib import CookieJar
try:
    import json
except ImportError:
    import simplejson as json
import logging
import os
from os import path
import shutil
import tarfile
import time
from urlparse import urljoin, urlsplit
from uuid import uuid1
import zipfile

import requests

import defaults

log = logging.getLogger(__name__)

class Remote(object):
    POLL_DELAY = 10

    def __init__(self, config):
        'Start new remote WebMynd builds'
        self.config = config
        self.cookies = CookieJar()
        self._authenticated = False
        self.app_config_file = 'app-%s.json' % self.config.get('main.uuid')

    @property
    def server(self):
        return self.config.get('main.server', default='http://www.webmynd.com/api/')
    def _csrf_token(self):
        for cookie in self.cookies:
            if cookie.name == 'csrftoken':
                return cookie.value
        else:
            raise Exception("We don't have a CSRF token")
        
    def _post(self, *args, **kw):
        error_message = kw.get('error_message', 'POST to %(url)s failed: status code %(status_code)s\n%(content)s')
        data = kw.get('data', {})
        data['csrfmiddlewaretoken'] = self._csrf_token()
        kw['data'] = data
        kw['cookies'] = self.cookies
        resp = requests.post(*args, **kw)
        if not resp.ok:
            try:
                msg = error_message % resp.__dict__
            except KeyError: # in case error_message is looking for something resp doesn't have
                msg = 'POST to %s failed %s: %s' % (
                    getattr(resp, 'url', 'unknown URL'),
                    str(resp),
                    getattr(resp, 'content', 'unknown error')
                )
            raise Exception(msg)
        return resp
    def _get(self, *args, **kw):
        error_message = kw.get('error_message', 'GET from %(url)s failed: status code %(status_code)s\n%(content)s')
        kw['cookies'] = self.cookies
        resp = requests.get(*args, **kw)
        if not resp.ok:
            try:
                msg = error_message % resp.__dict__
            except KeyError: # in case error_message is looking for something resp doesn't have
                msg = 'GET from %s failed %s: %s' % (
                    getattr(resp, 'url', 'unknown URL'),
                    str(resp),
                    getattr(resp, 'content', 'unknown error')
                )
            raise Exception(msg)
        return resp
        
    def _authenticate(self):
        if self._authenticated:
            log.debug('already authenticated - continuing')
            return
        log.info('authenticating as "%s"' % self.config.get('authentication.username'))
        credentials = {
            'username': self.config.get('authentication.username'),
            'password': self.config.get('authentication.password')
        }
        resp = self._get(urljoin(self.server, 'auth/hello'))
            
        resp = self._post(urljoin(self.server, 'auth/verify'), data=credentials)
        log.info('authentication successful')
        self._authenticated = True
        
    def latest(self):
        '''Get the ID of the latest completed production build for this app.'''
        log.info('fetching latest build ID')
        self._authenticate()
        
        resp = self._get(urljoin(self.server, 'app/%s/latest/' % self.config.get('main.uuid')))
        return json.loads(resp.content)['build_id']
        
    def fetch_unpackaged(self, build_id, to_dir='development'):
        '''Retrieves the unpackaged artefacts for a particular build.
        
        :param build_id: primary key of the build
        :param to_dir: directory that will hold all the unpackged build trees
        '''
        log.info('fetching unpackaged artefacts for build %s into "%s"' % (build_id, to_dir))
        self._authenticate()
        
        resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
        content = json.loads(resp.content)

        filenames = []
        orig_dir = os.getcwd()
        to_dir = path.abspath(to_dir)
        if not path.isdir(to_dir):
            log.warning('creating output directory "%s"' % to_dir)
            os.mkdir(to_dir)
        try:
            os.chdir(to_dir)
            unpackaged = content['unpackaged']
            available_platforms = [plat for plat, url in unpackaged.iteritems() if url]
            for platform in available_platforms:
                filename = urlsplit(unpackaged[platform]).path.split('/')[-1]
                full_filename = path.abspath(filename)
                resp = self._get(unpackaged[platform])
                with open(full_filename, 'w') as out_file:
                    log.debug('writing %s to %s' % (unpackaged[platform], full_filename))
                    out_file.write(resp.content)
                # unzip source trees to directories named after platforms
                zipf = zipfile.ZipFile(full_filename)
                shutil.rmtree(platform, ignore_errors=True)
                log.debug('removed "%s" directory' % platform)
                zipf.extractall()
                log.debug('extracted unpackaged build for %s' % platform)
                os.remove(full_filename)
                log.debug('removed downloaded file "%s"' % full_filename)
                filenames.append(path.abspath(platform))
        finally:
            os.chdir(orig_dir)
        
        log.info('fetched build into "%s"' % '", "'.join(filenames))
        return filenames
    
    def build(self, development=True, template_only=False):
        log.info('starting new build')
        self._authenticate()

        data = {}
        if path.isfile(self.app_config_file):
            with open(self.app_config_file) as app_config:
                data['config'] = app_config.read()

        def build_request(files=None):
            path = 'app/%s/%s/%s' % (
                self.config.get('main.uuid'),
                'template' if template_only else 'build',
                'development' if development else ''
            )
            url = urljoin(self.server, path)
            return self._post(url, data=data, files=files)
            
        user_dir = defaults.USER_DIR
        if template_only or not path.isdir(user_dir):
            if not path.isdir(user_dir):
                log.warning('no "user" directory found - we will be using the App\'s default code!')
            resp = build_request()
        else:
            filename, tar_file, orig_dir = 'user.%s.tar.bz2' % time.time(), None, os.getcwd()
            try:
                user_comp = None
                user_comp = tarfile.open(filename, mode='w:bz2')
                os.chdir(user_dir)
                for f in os.listdir('.'):
                    user_comp.add(f)
                    log.debug('added "%s" to user archive' % f)
                os.chdir(orig_dir)
        
                with open(filename, mode='r') as user_comp:
                    resp = build_request({'user.tar.bz2': user_comp})
            finally:
                try:
                    os.remove(filename)
                    if user_comp is not None:
                        user_comp.close()
                except OSError:
                    # wasn't created
                    pass

        build_id = json.loads(resp.content)['build_id']
        log.info('build %s started...' % build_id)
        
        resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
        content = json.loads(resp.content)
        while content['state'] in ('pending', 'working'):
            log.debug('build %s is %s...' % (build_id, content['state']))
            time.sleep(self.POLL_DELAY)
            resp = self._get(urljoin(self.server, 'build/%d/detail/' % build_id))
            content = json.loads(resp.content)
            
        if content['state'] in ('complete',):
            log.info('build completed successfully')
            log.debug(content['log_output'])
            return build_id
        else:
            raise Exception('build failed: %s' % content['log_output'])
    
    def get_app_config(self, build_id):
        'Fetch remote App configuration and save to local file'
        log.info('fetching remote App configuration for build %s' % build_id)
        self._authenticate()
        resp = self._get(urljoin(self.server, 'build/%d/config/' % build_id))
        config = json.loads(json.loads(resp.content)['config'])
        with open(self.app_config_file, 'w') as out_file:
            out_file.write(json.dumps(config, indent=4))
        log.info('wrote App configuration for build %d to "%s"' % (build_id, self.app_config_file))
        return self.app_config_file
        
    def get_latest_user_code(self, to_dir=defaults.USER_DIR):
        '''Fetch the customer's code archive attached to this app
        
        :param to_dir: directory to place the user code into
        '''
        log.info('fetching customer code')
        if path.exists(to_dir):
            raise Exception('"%s" directory already exists: cannot continue' % to_dir)
        self._authenticate()
        
        resp = self._get(urljoin(self.server, 'app/%s/code/' % self.config.get('main.uuid')))
        code_url = json.loads(resp.content)['code_url']
        log.debug('customer code is at %s' % code_url)
        resp = self._get(code_url)
        
        tmp_filename = path.abspath(uuid1().hex)
        with open(tmp_filename, 'w') as tmp_file:
            tmp_file.write(resp.read())
        os.mkdir(to_dir)
        orig_dir = os.getcwd()
        try:
            os.chdir(to_dir)
            tar_file = None
            tar_file = tarfile.open(tmp_filename)
            log.info('extracting customer code')
            tar_file.extractall()
        finally:
            os.chdir(orig_dir)
            if tar_file is not None:
                tar_file.close()
            log.debug('removing temporary file %s' % tmp_filename)
            os.remove(tmp_filename)