from setuptools import setup, find_packages
import sys, os

import forge

version = forge.VERSION

setup(name='Forge Build Tools',
	version=version,
	author='James Brady',
	author_email='james@trigger.io',
	url='https://trigger.io/',
	license='MIT',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	include_package_data=True,
	zip_safe=False,
	test_suite="nose.collector",
	setup_requires=['nose>=0.11'],
	install_requires=[]
)
