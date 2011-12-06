import re

from nose.tools import ok_

def assert_raises_regexp(exc, regex, to_call, *args, **kw):
	'''Check that to_call(*args, **kw) raises an exception of type
	:param:`exc`, whose string value matches the given :param:`regex`
	
	:param exc: an ``type`` of :class:`Exception` to catch
	:param regex: a regular expression string which we will match against
		the stringified exception
	:type regex: string
	:param to_call: the callable which should error out
	'''
	try:
		to_call(*args, **kw)
	except exc, e:
		ok_(
			re.compile(regex).search(str(e)),
			'Raised exception did not match "%s": "%s"' % (regex, str(e))
		)
	except Exception, e:
		ok_(False, 'Raised exception is not a %s: %s' % (exc, type(e)))
	else:
		ok_(False, '%s did not raise an exception' % to_call)