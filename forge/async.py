import threading
import logging
import traceback
import uuid
import Queue


LOG = logging.getLogger(__name__)
_async_storage = threading.local()


def current_call():
	"""Returns the Call object assigned to this thread, making it easy to emit events happening
	in the current Call without passing it around.
	"""
	return _async_storage.current_call


class CallInterrupted(Exception):
	"""Exception to be thrown when a Call is marked as interrupted"""
	def __init__(self):
		Exception.__init__(self, "Got kill signal")


def _run_call(call):
	"""We use this as our starting point for RPC calls. We need a top level function
	as a starting point in the case where we want to start a call in a new process.
	"""
	call.run()


# TODO: remove isolation level from this class, it should be reusable no matter what context
# it is run in, just requires appropriate queues for input/output to be handed to it
class Call(object):
	"""Allows remote calls to emit events back to whoever invoked it, as well as listen for
	responses to those events.

	e.g. log messages, progress bar, notifications, and success or error.
	"""
	def __init__(self, call_id, target, output, input, isolation_level, args=None, kwargs=None):
		self._call_id = call_id
		self._output = output
		self._input = input
		self._responses = {}
		self._interrupted = False
		self._target = target
		self._args = args or ()
		self._kwargs = kwargs or {}
		self._isolation_level = isolation_level

	def run(self):
		"""Run this in a dedicated thread"""
		if self._isolation_level == 'process':
			for h in logging.root.handlers[:]:
				logging.root.removeHandler(h)

		# store our Call object in a thread local so we can easily grab it and emit events
		_async_storage.current_call = self

		# create workers to distribute responses and wait for an interrupt
		self.setup_response_processing()

		# setup a logging.Handler which captures logging activity from the current thread and emits corresponding events
		handler = CallHandler(self, threading.current_thread().ident)
		handler.setLevel(logging.DEBUG)
		logging.root.addHandler(handler)
		logging.root.setLevel(logging.DEBUG)

		try:
			result = self._target(*self._args, **self._kwargs)

		# turn any return value or exception into a success or error event
		except Exception as e:
			# TODO: consider using e.__class__.__module__ for providing qualified exception types?
			import sys
			self.exception = sys.exc_info()[0]
			self.emit('error', check_for_interrupt=False, message=str(e), error_type=str(e.__class__.__name__), traceback=traceback.format_exc(e))
		else:
			self.emit('success', check_for_interrupt=False, data=result)

		finally:
			logging.root.removeHandler(handler)
			self._shutdown_input_handling_thread()

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
		if check_for_interrupt:
			self.assert_not_interrupted()
		event_id = str(uuid.uuid4())
		event = {
			'callId': self._call_id,
			'type': event_type,
			'eventId': event_id,
		}
		event = dict(event, **kwargs)
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
		return self._responses[event_id].get(block=True, timeout=timeout)


class CallHandler(logging.Handler):
	"""Captures logging activity on a specific thread and emits events for the
	call corresponding to that thread.
	"""
	def __init__(self, call, thread_ident, *args, **kwargs):
		logging.Handler.__init__(self, *args, **kwargs)
		self._call = call
		self._thread_ident = thread_ident

	def emit(self, record):
		if record.thread == self._thread_ident:
			self._call.emit('log', level=record.levelname, message=record.getMessage())
