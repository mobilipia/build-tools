"""Helpers for cli interaction"""
import sys
import math


def ask_question(question):
	message = question.get('message', '')
	choices = question.get('choices', [])
	lines = [" (%d) %s" % (i + 1, c) for i, c in enumerate(choices)]

	print "\n" + message + "\n" + "\n".join(lines)

	prompt = "Enter a choice between 1-%d: " % len(choices)
	choice = None
	while choice is None:
		try:
			inp = raw_input("\n" + prompt)
			n = int(inp.strip())

			if not (1 <= n <= len(choices)):
				raise ValueError

			choice = n
		except ValueError:
			print "Invalid choice"

	return choice

def _print_progress(width, message, fraction):
	filled = int(math.floor(width * fraction))
	unfilled = width - filled
	
	sys.stdout.write('%30s [%s%s]' % (
		message, '=' * filled, ' ' * unfilled
	))
	sys.stdout.flush()

def start_progress(progress_event, width=50):
	_print_progress(width, progress_event['message'], 0)

def log(level, message):
	print "[%7s] %s" % (level, message)

def info(message):
	log('INFO', message)

def error(message):
	log('ERROR', message)

def debug(message):
	log('DEBUG', message)

def end_progress(progress_event, width=50):
	sys.stdout.write('\n')

def progress_bar(progress_event, width=50):
	# called with
	fraction = progress_event['fraction']
	message = progress_event['message']

	# go back to start of line so can redraw on top of this
	sys.stdout.write('\r')

	_print_progress(width, message, fraction)
