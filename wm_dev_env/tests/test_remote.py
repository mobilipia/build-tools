import json

from wm_dev_env import BuildConfig, Remote

from mock import Mock, patch
from nose.tools import raises, assert_raises_regexp, assert_equals, assert_not_equals, assert_true, assert_false

class TestRemote(object):
    def setup(self):
        self.test_config = BuildConfig._test_instance()
        self.remote = Remote(self.test_config)
    
    def test_nocsrf(self):
        assert_raises_regexp(Exception, "don't have a CSRF token", self.remote._csrf_token)
    
    def test_latest(self):
        self.remote._authenticate = Mock()
        get_resp = Mock()
        get_resp.content = json.dumps({'build_id': -1})
        self.remote._get = Mock(return_value=get_resp)
        resp = self.remote.latest()
        assert_equals(resp, -1)
        self.remote._authenticate.assert_called_once_with( )
        self.remote._get.assert_called_once_with('http://www.webmynd.com/api/app/TEST-UUID/latest/')
        
    @patch('zipfile.ZipFile')
    def test_fetch_unpackaged(self, zipf):
        self.remote._authenticate = Mock()
        get_resp = Mock()
        get_resp.content = json.dumps({'unpackaged':{'chrome': 'chrome url', 'firefox': 'firefox url'}})
        self.remote._get = Mock(return_value=get_resp)
        resp = self.remote.fetch_unpackaged(-1, 'output dir')
        assert_true(zipf.call_args_list[0][0][0].endswith('/output dir/chrome url'))
        assert_true(zipf.call_args_list[1][0][0].endswith('/output dir/firefox url'))
        assert_equals(zipf.return_value.extractall.call_count, 2)
        assert_true(resp[0].endswith('/output dir/chrome'))
        assert_true(resp[1].endswith('/output dir/firefox'))
    
    def test_build(self):
        self.remote._authenticate = Mock()
        post_resp = Mock()
        post_resp.content = json.dumps({'build_id': -1})
        self.remote._post = Mock(return_value=post_resp)
        get_resp = Mock()
        get_resp.content = json.dumps({'build_id': -1, 'state': 'complete', 'log_output': 'test logging'})
        self.remote._get = Mock(return_value=get_resp)
        resp = self.remote.build()
        assert_equals(resp, -1)