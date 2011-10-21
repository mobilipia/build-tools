import subprocess
import logging
import os
import signal
from os import path
import time
from glob import glob

from webmynd import ForgeError

LOG = logging.getLogger(__name__)

class IOSRunner(object):
	def __init__(self):
		self.log_process = None
		self.sdk = '/Developer/Platforms/iPhoneSimulator.platform/Developer/Applications/iPhone Simulator.app/Contents/MacOS'

		if not path.exists(self.sdk):
			raise ForgeError("Couldn't find the iPhone sdk at: %s" % self.sdk)

	@staticmethod
	def get_child_processes(target_parent_pid):
		'Gets processes which have the given pid as their parent'
		# scrape processes for those with the iphone simulator as the parent
		list_processes = subprocess.Popen('ps ax -o "pid= ppid="', shell=True, stdout=subprocess.PIPE)

		child_pids = []

		for line in list_processes.stdout:
			line = line.strip()
			if line != "":
				pid, parent_pid = map(int, line.split())
				if parent_pid == target_parent_pid:
					child_pids.append(pid)

		return child_pids

	def start_piping_system_log(self, app_name, pid):
		LOG.info('Showing log output:')
		self.log_process = subprocess.Popen(r"tail -f /var/log/system.log | grep --line-buffered '\[%s' | sed -E 's/([^ ]+ [^ ]+ [^ ]+).*\]: (.*)/[\1] \2/'" % pid, shell=True)

	def run_iphone_simulator_with(self, app_name):
		try:
			path_to_app = glob('./development/ios/simulator-*/%s' % app_name)[0]
			path_to_simulator = path.join(self.sdk, "iPhone Simulator")
			path_to_file = path.abspath(path_to_app)

			LOG.debug('trying to run app %s' % path_to_file)
			simulator = subprocess.Popen([path_to_simulator, "-SimulateApplication", path_to_file])
			LOG.info('simulator pid is %s' % simulator.pid)

			# XXX: race condition, the app may not have started yet, so we try a few times.
			app_pid = None
			attempts = 0

			while app_pid is None:
				time.sleep(0.5)
				child_processes = self.get_child_processes(simulator.pid)

				if child_processes:
					app_pid = child_processes[0]
					LOG.info("pid for iPhone app is: %s" % app_pid)
					break

				if app_pid is None:
					attempts += 1

				if attempts > 10:
					LOG.info("failed to get pid for the app being simulated. This means we can't kill it on shutdown, so you may have to kill it yourself using Activity Monitor")
					break

			self.start_piping_system_log(app_name, app_pid)
			simulator.communicate()

		finally:
			if app_pid is not None:
				LOG.debug('sending kill signal to simulated app...')
				os.kill(app_pid, signal.SIGTERM)
