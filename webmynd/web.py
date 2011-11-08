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
def index():
	return "Hello world"

@route('/app')
@json_view
def apps():
	"""
	Returns a list of App details as JSON
	"""
	return remote.list_apps()

@route('/static/:filename')
def server_static(filename):
	return static_file(filename, root='static/')

if __name__ == "__main__":
	run(host='localhost', port=5000)