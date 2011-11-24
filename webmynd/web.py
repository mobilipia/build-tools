import json
from bottle import route, run, static_file
from webmynd.remote import Remote

remote = Remote({})

def json_view(view):
	def with_json_response(*args, **kwargs):
		response = view(*args, **kwargs)
		return json.dumps(response)

	return with_json_response

@route('/')
def _index():
	return "Hello world"

@route('/app')
@json_view
def _apps():
	"""
	Returns a list of App details as JSON
	"""
	return remote.list_apps()

@route('/static/:filename')
def _server_static(filename):
	return static_file(filename, root='static/')

def run_server():
	run(host='localhost', port=5000)