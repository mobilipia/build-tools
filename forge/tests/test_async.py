from forge import async
from nose.tools import eq_


class TestExtraErrorProperties(object):
	def test_should_return_empty_dict_when_no_extra_method_available(self):
		extra = async._extra_error_properties(Exception("hi"))
		eq_(extra, {})

	def test_should_return_result_of_extra_method(self):
		class DummyException(Exception):
			def extra(self):
				return {'foo': 2, 'bar': 3}

		extra = async._extra_error_properties(DummyException("hi"))
		eq_(extra, {'foo': 2, 'bar': 3})
