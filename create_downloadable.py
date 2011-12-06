from zipfile import ZipFile

import os
from os import path
import zipfile

def add_folder_to_zip(folder, archive_path_prefix, zip):
	for root, dirs, files in os.walk(folder):
		for f in files:
			path_to_file = path.join(root, f)
			print "adding: ", path_to_file
			archive_name = path.join(archive_path_prefix, path_to_file)

			zip.write(path_to_file, archive_name)

if __name__ == "__main__":

	required_folders = [
		'scripts',
		'forge',
		'forge-dependencies',
	]

	required_files = [
		'go.sh',
		'go.bat',
		'common.sh',

		'debug.keystore',
		'README.rst',
		'forge_build.json'
	]

	with ZipFile('forge-tools.zip', 'w') as distributable:
		for f in required_folders:
			add_folder_to_zip(f, 'forge-tools', distributable)

		for r in required_files:
			distributable.write(r, path.join('forge-tools', r))
