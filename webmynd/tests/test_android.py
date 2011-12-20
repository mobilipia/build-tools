from mock import Mock, patch
from nose.tools import eq_, ok_, raises
	
from webmynd import android
from webmynd.tests.lib import assert_raises_regexp

class TestLookForJava(object):
	@patch('webmynd.android.os.path.isdir')
	def test_all_there(self, isdir):
		isdir.return_value = True
		
		eq_(len(android._look_for_java()), 4)
	@patch('webmynd.android.os.path.isdir')
	def test_none_there(self, isdir):
		isdir.return_value = False
		
		eq_(len(android._look_for_java()), 0)

class TestDownloadForWindows(object):
	@patch('webmynd.android.zipfile')
	@patch('webmynd.android.urllib')
	def test_normal(self, urllib, zipfile):
		res = android._download_sdk_for_windows()
		
		eq_(urllib.urlretrieve.call_args[0][0], "http://webmynd.com/redirect/android/windows")
		
		zipfile.ZipFile.assert_called_once()
		zipfile.ZipFile.return_value.extractall.assert_called_once()
		zipfile.ZipFile.return_value.close.assert_called_once()
		
		eq_(res.android, r"C:\android-sdk-windows\tools\android.bat")
		eq_(res.adb, r"C:\android-sdk-windows\platform-tools\adb")

class TestDownloadForMac(object):
	@patch('webmynd.android.Popen')
	@patch('webmynd.android.urllib')
	def test_normal(self, urllib, Popen):
		Popen.return_value.communicate.return_value = ('', '')
		res = android._download_sdk_for_mac()
		
		eq_(urllib.urlretrieve.call_args[0][0], "http://webmynd.com/redirect/android/macosx")
		
		Popen.assert_called_once()
		
		eq_(res.android, r"/Applications/android-sdk-macosx/tools/android")
		eq_(res.adb, r"/Applications/android-sdk-macosx/platform-tools/adb")

class TestDownloadForLinux(object):
	@patch('webmynd.android.Popen')
	@patch('webmynd.android.urllib')
	@patch('webmynd.android.os')
	@patch('webmynd.android.path')
	def test_normal(self, path, os, urllib, Popen):
		path.isdir.return_value = False
		Popen.return_value.communicate.return_value = ('', '')
		res = android._download_sdk_for_linux()
		
		eq_(urllib.urlretrieve.call_args[0][0], "http://webmynd.com/redirect/android/linux")
		
		os.mkdir.assert_called_once()
		Popen.assert_called_once()
		
		ok_(res.android.endswith("/android-sdk-macosx/tools/android"))
		ok_(res.adb.endswith("/android-sdk-macosx/platform-tools/adb"))
		
	@patch('webmynd.android.Popen')
	@patch('webmynd.android.urllib')
	@patch('webmynd.android.os')
	@patch('webmynd.android.path')
	def test_normal(self, path, os, urllib, Popen):
		path.isdir.return_value = True
		Popen.return_value.communicate.return_value = ('', '')
		res = android._download_sdk_for_linux()
		
		eq_(os.mkdir.call_count, 0)
		
class TestInstallSdk(object):
	@patch('webmynd.android._check_for_sdk')
	@patch('webmynd.android._update_sdk')
	@patch('webmynd.android._download_sdk_for_windows')
	@patch('webmynd.android.os.chdir')
	@patch('webmynd.android.tempfile.mkdtemp')
	@patch('webmynd.android.shutil.rmtree')
	@patch('webmynd.android.sys')
	def test_win(self, sys, rmtree, mkdtemp, chdir, _download_sdk_for_windows, _update_sdk, _check_for_sdk):
		sys.platform = 'windows'
		
		res = android._install_sdk_automatically()
		
		_download_sdk_for_windows.assert_called_once()
		_update_sdk.assert_called_once_with(android._download_sdk_for_windows.return_value)
		eq_(res, _check_for_sdk.return_value)
		rmtree.assert_called_once_with(mkdtemp.return_value, ignore_errors=True)

	@patch('webmynd.android._check_for_sdk')
	@patch('webmynd.android._update_sdk')
	@patch('webmynd.android._download_sdk_for_mac')
	@patch('webmynd.android.os.chdir')
	@patch('webmynd.android.tempfile.mkdtemp')
	@patch('webmynd.android.shutil.rmtree')
	@patch('webmynd.android.sys')
	def test_mac(self, sys, rmtree, mkdtemp, chdir, _download_sdk_for_mac, _update_sdk, _check_for_sdk):
		sys.platform = 'darwin'
		
		res = android._install_sdk_automatically()
		
		_download_sdk_for_mac.assert_called_once()
		_update_sdk.assert_called_once_with(_download_sdk_for_mac.return_value)

	@patch('webmynd.android._check_for_sdk')
	@patch('webmynd.android._update_sdk')
	@patch('webmynd.android._download_sdk_for_linux')
	@patch('webmynd.android.os.chdir')
	@patch('webmynd.android.tempfile.mkdtemp')
	@patch('webmynd.android.shutil.rmtree')
	@patch('webmynd.android.sys')
	def test_linux(self, sys, rmtree, mkdtemp, chdir, _download_sdk_for_linux, _update_sdk, _check_for_sdk):
		sys.platform = 'linux'
		
		res = android._install_sdk_automatically()
		
		_download_sdk_for_linux.assert_called_once()
		_update_sdk.assert_called_once_with(_download_sdk_for_linux.return_value)

	@raises(android.CouldNotLocate)
	@patch('webmynd.android._check_for_sdk')
	@patch('webmynd.android._update_sdk')
	@patch('webmynd.android._download_sdk_for_windows')
	@patch('webmynd.android.os.chdir')
	@patch('webmynd.android.tempfile.mkdtemp')
	@patch('webmynd.android.shutil.rmtree')
	@patch('webmynd.android.sys')
	def test_error(self, sys, rmtree, mkdtemp, chdir, _download_sdk_for_windows, _update_sdk, _check_for_sdk):
		sys.platform = 'windows'
		_download_sdk_for_windows.side_effect=Exception
		
		res = android._install_sdk_automatically()

class TestUpdateSdk(object):
	@patch('webmynd.android.time')
	@patch('webmynd.android.Popen')
	def test_normal(self, Popen, time):
		popen_poll = [None, 0]
		def poll():
			return popen_poll.pop(0)
		Popen.return_value.poll.side_effect = poll
		
		android._update_sdk(android.PathInfo(adb='adb', android='android', sdk='sdk'))
		eq_(Popen.call_args_list[0][0][0], ['android', "update", "sdk", "--no-ui", "--filter", "platform-tool,tool,android-8"])
		eq_(Popen.call_args_list[1][0][0], ["adb", "kill-server"])

class TestShouldInstallSdk(object):
	def test_answer_1(self):
		mock_raw_input = Mock()
		mock_raw_input.return_value = '1'
		with patch('__builtin__.raw_input', mock_raw_input):
			result = android._should_install_sdk('dummy path')
		
		assert result
	def test_answer_2(self):
		mock_raw_input = Mock()
		mock_raw_input.return_value = '2'
		with patch('__builtin__.raw_input', mock_raw_input):
			result = android._should_install_sdk('dummy path')
		
		assert not result
	def test_answer_y_then_2(self):
		y2 = ['y', '2']
		def y_then_2(*args, **kw):
			return y2.pop(0)
		mock_raw_input = Mock()
		mock_raw_input.side_effect = y_then_2
		with patch('__builtin__.raw_input', mock_raw_input):
			result = android._should_install_sdk('dummy path')
		
		assert not result

class TestCheckForSdk(object):
	@patch('webmynd.android.path')
	def test_found_manual_no_slash(self, path):
		path.isdir = lambda pth: pth == 'manual sdk'

		res = android._check_for_sdk('manual sdk')
		
		eq_(res, 'manual sdk/')
	@patch('webmynd.android.path')
	def test_found_manual(self, path):
		path.isdir = lambda pth: pth == 'manual sdk/'

		res = android._check_for_sdk('manual sdk/')
		
		eq_(res, 'manual sdk/')
	@patch('webmynd.android.path')
	def test_found_default(self, path):
		path.isdir = lambda pth: pth == "C:/android-sdk-windows/"
		res = android._check_for_sdk()
		eq_(res, "C:/android-sdk-windows/")
	
	@patch('webmynd.android._should_install_sdk')
	@patch('webmynd.android.path')
	def test_choose_manual(self, path, _should_install_sdk):
		path.isdir.return_value = False
		_should_install_sdk.return_value = False
		
		assert_raises_regexp(android.CouldNotLocate, "please install one", android._check_for_sdk)
		
	@patch('webmynd.android.sys')
	@patch('webmynd.android.path')
	def test_funny_platform(self, path, sys):
		path.isdir.return_value = False
		sys.platform = 'mismatch'
		
		assert_raises_regexp(android.CouldNotLocate, "please specify with", android._check_for_sdk)
		
	@patch('webmynd.android._install_sdk_automatically')
	@patch('webmynd.android._should_install_sdk')
	@patch('webmynd.android.path')
	def test_choose_auto(self, path, _should_install_sdk, _install_sdk_automatically):
		path.isdir.return_value = False
		_should_install_sdk.return_value = True
		
		android._check_for_sdk()

		_install_sdk_automatically.assert_called_once()

class TestScrapeDevices(object):
	def test_normal(self):
		text = '''\
List of devices attached 
012345A	device
012345B	device
'''
		eq_(android._scrape_available_devices(text), ["012345A", "012345B"])
