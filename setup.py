from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='WebMynd Development Environment',
    version=version,
    description="",
    long_description="""\
    """,
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='',
    author='James Brady',
    author_email='james@webmynd.com',
    url='http://www.webmynd.com/',
    license='Closed source',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'requests', 'argparse'
    ],
    entry_points={
        'console_scripts': [
            'wm-refresh = webmynd.main:refresh',
            'wm-init = webmynd.main:init',
            'wm-dev-build = webmynd.main:development_build',
            'wm-prod-build = webmynd.main:production_build',
        ]
    }
)
