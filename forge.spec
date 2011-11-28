"""Specification for how to build the forge executable

Instructions for use
====================

Windows
-------
install pyinstaller
install pywin32 library
C:\Python27\python C:\path\to\pyinstaller.py forge.spec

PyInstaller
===========

api docs for writing spec files: http://www.pyinstaller.org/export/latest/trunk/doc/Manual.html#spec-files

"""

# TODO: should we be using pyinstaller straight from svn or the official release?
# the release I'm using has a lot of warnings and I'm unsure whether they matter

#W:Traceback (most recent call last):
#  File "C:\Users\Tim Monks\programs\pyinstaller-1.5.1\bindepend.py", line 683, in getImports
#    return _getImports_pe_lib_pefile(pth)
#  File "C:\Users\Tim Monks\programs\pyinstaller-1.5.1\bindepend.py", line 191, in _getImports_pe_lib_pefile
#    for entry in pe.DIRECTORY_ENTRY_IMPORT:
#AttributeError: PE instance has no attribute 'DIRECTORY_ENTRY_IMPORT'

import os

# this figures out what python modules are dependencies for our program, and where
# they are in the filesystem so they can be copied into a bundle
a = Analysis([
	# files to analyse for dependencies
	# HOMEPATH refers to the path to the pyinstaller installation
	os.path.join(HOMEPATH,'support', '_mountzlib.py'),
	os.path.join(HOMEPATH,'support', 'useUnicode.py'),
	os.path.join('webmynd', 'main.py'),
],[
	# path of places to grab dependencies from (the standard python 3rd party library directories
	# are also searched)
	os.getcwd(),
	os.path.join(os.getcwd(), 'webmynd-dependencies'),
], hookspath=[
	os.path.join(os.getcwd(), 'pyinstaller-hooks')
],
)

# pyz just means a compressed (z for zipped, though you can specify the compression algorithm)
# set of python files, I think.
pyz = PYZ(
	# a.pure refers to the pure python dependencies identified by the above
	# dependency Analysis.
	a.pure,
)

def _toc(*args, **kwargs):
	entry_type = kwargs.get('type', 'DATA')

	entries = []
	for path in args:
		full_path = os.path.abspath(path)
		entries.append(
			(path, full_path, entry_type)
		)

	return entries

forced_data_dependencies = _toc(
	'webmynd/apk-signer.jar',
	type='DATA'
)

print "FORCED DATA DEPENDENCIES"
for x in forced_data_dependencies:
	print x

exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.zipfiles,
	a.datas + forced_data_dependencies,

	# the output location of the exe
	name=os.path.join('dist', 'forge.exe'),

	# no idea
	debug=False,

	# TODO: strip might be useful to have on?
	strip=False,

	# no idea
	upx=True,

	# might want to set this to false for the webserver
	console=True,

	icon='forge.ico'
)