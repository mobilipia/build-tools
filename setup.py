from setuptools import setup, find_packages
import sys, os

version = '0.2.5'

setup(name='WebMynd Build Tools',
	version=version,
	author='James Brady',
	author_email='james@webmynd.com',
	url='http://www.webmynd.com/',
	license='MIT',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	include_package_data=True,
	zip_safe=False,
	test_suite="nose.collector",
	setup_requires=['nose>=0.11'],
	install_requires=[],
	entry_points={
		'console_scripts': [
			'wm-refresh = webmynd.main:refresh',
			'wm-init = webmynd.main:init',
			'wm-dev-build = webmynd.main:development_build',
			'wm-prod-build = webmynd.main:production_build',
		]
	}
)