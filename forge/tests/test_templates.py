import mock
from nose.tools import eq_, ok_
from os import path

from forge import defaults
from forge.templates import Manager
from forge.tests import dummy_config

class Test_HashFile(object):
	def setup(self):
		self.manager = Manager(dummy_config())
		
	def test_normal(self):
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		manager.read.return_value = 'the contents of the hash file'
		
		with mock.patch('forge.templates.codecs.open', new=mock_open):
			hsh = self.manager._hash_file('config file name')
		
		eq_(hsh, 'd633bf2dfeecd2a8561d736ff0db50ee')


class TestTemplatesFor(object):
	def setup(self):
		self.manager = Manager(dummy_config(), '.my-templates')
		
	@mock.patch('forge.templates.path')
	def test_exists(self, path):
		path.join.return_value = 'the hash file'
		path.exists.return_value = True
		self.manager._hash_file = mock.Mock()
		self.manager._hash_file.return_value = '999'
		
		res = self.manager.templates_for_config()
		
		self.manager._hash_file.assert_called_once_with('config filename')
		path.join.assert_called_once_with('.my-templates', '999.hash')
		eq_(res, '.my-templates')
		
	@mock.patch('forge.templates.path')
	def test_not_exists(self, path):
		path.join.return_value = 'the hash file'
		path.exists.return_value = False
		self.manager._hash_file = mock.Mock()
		self.manager._hash_file.return_value = '999'
		
		res = self.manager.templates_for_config()
		
		path.join.assert_called_once_with('.my-templates', '999.hash')
		eq_(res, None)

class TestFetchTemplates(object):
	def setup(self):
		self.manager = Manager(dummy_config(), 'templates')
		
	@mock.patch('forge.templates.shutil')
	@mock.patch('forge.templates.Remote')
	def test_no_templates(self, Remote, shutil):
		self.manager.templates_for_config = mock.Mock(return_value=None)
		self.manager._hash_file = mock.Mock(return_value='hashed file')
		remote = Remote.return_value
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		
		with mock.patch('__builtin__.open', new=mock_open):
			res = self.manager.fetch_templates(-1)
			
		self.manager.templates_for_config.assert_called_once_with()
		shutil.rmtree.assert_called_once_with('templates', ignore_errors=True)
		remote.fetch_unpackaged.assert_called_once_with(-1, to_dir='templates')
		mock_open.assert_called_once_with(path.join('templates', 'hashed file.hash'), 'w')
		ok_(manager.write.called)
		eq_(res, 'templates')
		
	@mock.patch('forge.templates.shutil')
	@mock.patch('forge.templates.Remote')
	def test_have_templates(self, Remote, shutil):
		self.manager.templates_for_config = mock.Mock(return_value='template directory')

		res = self.manager.fetch_templates(-1)
			
		eq_(res, 'template directory')
	
	@mock.patch('forge.templates.shutil')
	@mock.patch('forge.templates.Remote')
	def test_clean_templates_first(self, Remote, shutil):
		self.manager.templates_for_config = mock.Mock(return_value='template directory')
		self.manager._hash_file = mock.Mock(return_value='hashed file')
		remote = Remote.return_value
		mock_open = mock.MagicMock()
		manager = mock_open.return_value.__enter__.return_value
		
		with mock.patch('__builtin__.open', new=mock_open):
			res = self.manager.fetch_templates(-1, clean=True)
		
		shutil.rmtree.assert_called_once_with('templates', ignore_errors=True)
