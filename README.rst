WebMynd Development Tools
=========================
Note that this repository is currently mainly intended to aid tool distribution to our users: although we don't currently expect much community participation, pull requests are gratefully received!

Overview
--------
WebMynd aims to be as unobtrusive as possible as you're developing and testing your application.

This repository holds a number of command-line tools to work with your local WebMynd development environments, so that you can use whatever editor, build system and source control you want.

Requirements
------------
Python
~~~~~~
Install a version of `Python 2.x <http://www.python.org/getit/releases/>`_ , at least version 2.6.

You can check if you already have Python installed by running in a terminal:

{{{
$ python -V
Python 2.7.2
}}}

Please update your software if you have an unsupported version of Python, or you see something like:

{{{
$ python -V
-bash: python: command not found
}}}

Setuptools
~~~~~~~~~~
`Setuptools <http://pypi.python.org/pypi/setuptools#installation-instructions>`_ is a package manager for Python.

You may already have it installed: check by opening a terminal and running

{{{
easy_install
}}}

Virtualenv
~~~~~~~~~~
We'll use `virtualenv <http://pypi.python.org/pypi/virtualenv>`_ to provide an easy way to compartmentalise different Python projects.

After installing virtualenv, create a new virtual environment by running in a terminal:

{{{
virtualenv --no-site-packages webmynd-environment   # creates the environment
source webmynd-environment/bin/activate             # activates the environment
}}}

From now on, you will need to have activated this environment whenever working with the WebMynd tools.

Installation
------------
Download the WebMynd tools, by either getting the latest source or one of the pre-packaged downloads.

In a terminal, change directory into the newly extracted WebMynd Tools, and install them into your virtual environment:

{{{
cd webmynd-tools
python setup.py install

Configuration
~~~~~~~~~~~~~
The tools require a small amount of configuration. Copy the following into a new file called webmynd_configuration.json:

{{{
{
  "authentication": {
    "username": "your user name",
    "password": "your secret"
  },
  "main": {
    "uuid": "UUID for your app",
    "server": "http://generate.webmynd.com/api/"
  }
}
}}}
You should complete the authentication values with your username and password.
You can find the UUID for your app by going to `your apps <http://generate.webmynd.com/>`_ and clicking on the relevant one.

Creating a development environment
----------------------------------
The first command to run is "wm-init".

This command downloads the source and configuration for your app, and sets up the initial directory structure for you to develop in.

{{{
wm-init -c webmynd_configuration.json     # name the configuration file you created before 
}}}

This command will create three things:

* a "user" directory, which contains the JavaScript, HTML and CSS for your app
* a configuration file, named like "app-UUID-XXXX-XXXXXXXX.json", which contains the per-app configuration used when building your app
* a "development" directory, which contains generated add-ons for the various platforms you have enabled

Running your first build
------------------------
After running "wm-init", which should only be done once per development environment, we can run "wm-dev-build" as many times as we need to create local runnable apps for your app.

{{{
wm-dev-build -c webmynd_configuration.json
}}}

You will now have a "development" directory, under which there are a number of directories - one for each platform you have enabled for your app.

Understanding your development environment
------------------------------------------
You now have a "user" directory full of your source files, a configuration file which specifies how your app should be generated and run, and the "development" directory with runnable apps.

How to edit the source files is outside the scope of this document. Please see our other documentation we supplied for more information.

The generated add-ons in the "development" directory can be used directly in browsers. For more information, see:

* `Loading unpacked extensions <http://code.google.com/chrome/extensions/getstarted.html#load>`_ for Chrome
* `Extension proxy files <https://developer.mozilla.org/en/Setting_up_extension_development_environment#Firefox_extension_proxy_file>`_ for Firefox
* `Extension builder <http://developer.apple.com/library/safari/#documentation/Tools/Conceptual/SafariExtensionGuide/UsingExtensionBuilder/UsingExtensionBuilder.html>`_ for Safari

Expected workflow
-----------------
After every change to your source code, you should run "wm-dev-build" to re-create the runnable apps, before refreshing / restarting the affected browsers and verifying your changes have taken effect.

We've made a number of optimisations so that most work you do *which don't change your app configuration file* will be very quick to build.

ToDo here
---------

* example apps and tutorials
* links into API documentation