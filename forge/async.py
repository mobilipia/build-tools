import threading
import logging
import traceback
import uuid
import Queue
import sys


LOG = logging.getLogger(__name__)
_thread_local_call = None
_process_call = None


def set_current_call(call, thread_local):
	global _process_call, _thread_local_call
	if thread_local:
		_thread_local_call = call
	else:
		_process_call = call

def current_call():
	"""Returns the Call object assigned to this Process (only makes sense to call this from a build
	task isolated to a process)
	"""
	if _process_call:
		return _process_call

	if _thread_local_call:
		return _thread_local_call


class CallInterrupted(Exception):
	"""Exception to be thrown when a Call is marked as interrupted"""
	def __init__(self):
		Exception.__init__(self, "Got kill signal")


def _run_call(call):
	"""We use this as our starting point for RPC calls. We need a top level function
	as a starting point in the case where we want to start a call in a new process.
	"""
	call.run()


class Call(object):
	"""Wraps a function so that it can easily emit a stream of events while running, and
	listen for responses to those events.

	e.g. log messages, progress bar, notifications, and success or error.
	"""
	def __init__(self, call_id, target, output, input, stamp=None, args=None, kwargs=None):
		"""Construct a call, passing it anything that has the Queue interface for events.

		:param target: Target function to run and capture events for.
		
		:param output: Queue that the target function will put events into.
		:param input: Queue that the target function will read responses from.

		:param stamp: Optional dict of attributes to include in every emitted event.
		:param args: Positional arguments to invoke the target with.
		:param kwargs: Keyword arguments to invoke the target with.
		"""
		self._call_id = call_id
		self._stamp = stamp
		self._output = output
		self._input = input
		self._responses = {}
		self._interrupted = False
		self._target = target
		self._args = args or ()
		self._kwargs = kwargs or {}
		self._seen_interrupt = False

	def __str__(self):
		return "<Call(%s, %s)>" % (self._call_id, self._target)

	def run(self):
		"""Run the wrapped function until completion, converting the following into events:

		* Raising an uncaught exception causes an 'error' event.
		* Returning normally causes a 'success' event.
		"""
		# exceptions that aren't necessarily fatal
		EXPECTED_EXCEPTIONS = ('ForgeError',)
		
		# create workers to distribute responses and wait for an interrupt
		self.setup_response_processing()

		try:
			result = self._target(*self._args, **self._kwargs)

		# turn any return value or exception into a success or error event
		except Exception as e:
			# TODO: consider using e.__class__.__module__ for providing qualified exception types?
			event_type = 'error'
			event = dict(
				message=str(e),
				error_type=str(e.__class__.__name__),
				traceback=traceback.format_exc(e),
				expected=(e.__class__.__name__ in EXPECTED_EXCEPTIONS)
			)

			self.exception = sys.exc_info()[0]

		else:
			event_type = 'success'
			event = dict(
				data=result
			)

		finally:
			self._shutdown_input_handling_thread()

			self.emit(event_type, check_for_interrupt=False, **event)

	def setup_response_processing(self):
		"""Sets up a thread distributing responses to events, as well as a thread listening
		for interrupt responses.

		This logic would be in the constructor, except we need to defer it until this object
		has been passed to an external process (e.g. Threads/Locks can't be pickled for transfer).
		"""
		# Maps event IDs to queues. We use these to listen for
		# responses to individual events
		self._responses_lock = threading.Lock()

		input_handling_thread = threading.Thread(target=self._handle_input)
		input_handling_thread.daemon = True
		input_handling_thread.start()

	FINISHED = 9001
	INTERRUPTED = 9002

	def _handle_input(self):
		"""Continually reads from the input Queue for this Call and
		distributes the responses to separate Queues.
		"""
		while True:
			event = self._input.get()
			if event == Call.FINISHED:
				break

			if event == Call.INTERRUPTED:
				self._interrupted = True
				break

			event_id = event['eventId']
			created_queue = self._atomic_create_response_queue_if_necessary(event_id)
			
			if created_queue:
				LOG.warning("Received response to event %d, but was not expecting it yet" % event_id)

			self._responses[event_id].put(event)

	def _shutdown_input_handling_thread(self):
		self._input.put(Call.FINISHED)

	def assert_not_interrupted(self):
		"""Used occasionally in remote calls to see whether there has been a kill signal
		from the caller.
		"""
		if self._interrupted:
			self._seen_interrupt = True
			raise CallInterrupted

	# TODO: consistent protocol for messaging
	def emit(self, event_type, check_for_interrupt=True, **kwargs):
		"""Emit an event to the calling side of the session.

		:param event_type: The type of the event to emit
		:param check_for_interrupt: If this is True, then check if this Call has been interrupted before emitting
			and raise an exception if so (default: True)

		Emitted events are dicts that take the form:
		{
			callId: provided so the receiving end can identify which RPC this event came from,
			type: the type of this event for event handlers,
			eventId: a unique identifier for this event, for responses
		}
		"""
		if not self._seen_interrupt and check_for_interrupt:
			self.assert_not_interrupted()
		event_id = str(uuid.uuid4())
		event = {
			'callId': self._call_id,
			'type': event_type,
			'eventId': event_id,
		}
		event = dict(event, **kwargs)
		if self._stamp is not None:
			event.update(self._stamp)
		self._output.put(event)
		return event_id

	def input(self, response):
		"""Input a response to an event. A response is a dict with the form:

		{
			eventId: the id for the event that this is a response to,
			data: the content of the response
		}
		"""
		self._input.put(response)

	def interrupt(self):
		self._input.put(Call.INTERRUPTED)

	def _atomic_create_response_queue_if_necessary(self, event_id):
		"""Create a response queue for responses to a particular event

		:param event_id: Identifier for the event we want to be able to handle responses for.
		"""
		try:
			self._responses_lock.acquire()
			if event_id not in self._responses:
				self._responses[event_id] = Queue.Queue()
				return True
		finally:
			self._responses_lock.release()

	def wait_for_response(self, event_id, timeout=None):
		"""Wait for a response to a particular event

		:param event_id: ID for the event we want to wait for a response to.
		:param timeout: If None, wait forever for a response, otherwise wait for the number of seconds given.
		"""
		self._atomic_create_response_queue_if_necessary(event_id)
		while True:
			try:
				self.assert_not_interrupted()
				response = self._responses[event_id].get(block=True, timeout=1)
				return response
			except Queue.Empty:
				continue


class CallHandler(logging.Handler):
	"""Captures logging activity on a specific thread and emits events for the
	call corresponding to that thread.
	"""
	def __init__(self, call, *args, **kwargs):
		logging.Handler.__init__(self, *args, **kwargs)
		self._call = call

	def emit(self, record):
		self._call.emit('log', level=record.levelname, message=record.getMessage())
