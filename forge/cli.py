"""Helpers for cli interaction"""


def ask_question(question):
	message = question.get('message', '')
	choices = question.get('choices', [])
	lines = [" (%d) %s" % (i + 1, c) for i, c in enumerate(choices)]

	print message + "\n" + "\n".join(lines)

	prompt = "Enter a choice between 1-%d: " % len(choices)
	choice = None
	while choice is None:
		try:
			inp = raw_input(prompt)
			n = int(inp.strip())

			if not (1 <= n <= len(choices)):
				raise ValueError

			choice = n
		except ValueError:
			print "Invalid choice"

	return choice
