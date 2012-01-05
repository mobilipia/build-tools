Forge Development Tools
=========================
Note that this repository is currently mainly intended to aid tool distribution to our users: although we don't currently expect much community participation, pull requests are gratefully received!

Overview
--------
Forge aims to be as unobtrusive as possible as you're developing and testing your application.

This repository holds a number of command-line tools to work with your local Forge development environments, so that you can use whatever editor, build system and source control you want.

Getting Started
---------------

Run ``go.bat`` (on Windows) or ``source go.sh`` (on Mac and Linux) to install our dependencies and create a working environment for the build tools.

Creating a new app
------------------
Run ``wm-create`` to create a new app and set up your local development environment.

This command will create a ``user`` directory, with an initial app configuration file for you to customise.

This ``user`` directory is your app: it should be placed in version control and shared between team members.

Working on an existing app
--------------------------
Grab the ``user`` directory for your app from version control, or whatever method you're using to distribute source.

Running your first build
------------------------
After creating a new app, or getting the source for an existing app, we can run ``wm-dev-build`` to create local runnable builds for your app::

  wm-dev-build

You will now have a ``development`` directory, under which there are a number of directories - one for each platform you have enabled for your app.

Understanding your development environment
------------------------------------------
You now have a ``user`` directory full of your source files, a configuration file which specifies how your app should be generated and run, and the ``development`` directory with runnable apps.

How to edit the source files is outside the scope of this document. Please see our other documentation we supplied for more information.

The generated add-ons in the ``development`` directory can be used directly in browsers. For more information, see:

* `Loading unpacked extensions <http://code.google.com/chrome/extensions/getstarted.html#load>`_ for Chrome
* `Extension proxy files <https://developer.mozilla.org/en/Setting_up_extension_development_environment#Firefox_extension_proxy_file>`_ for Firefox
* `Extension builder <http://developer.apple.com/library/safari/#documentation/Tools/Conceptual/SafariExtensionGuide/UsingExtensionBuilder/UsingExtensionBuilder.html>`_ for Safari

Expected workflow
-----------------
After every change to your source code, you should run ``wm-dev-build`` to re-create the runnable apps, before refreshing / restarting the affected browsers and verifying your changes have taken effect.

We've made a number of optimisations so that most work you do *which don't change your app configuration file* will be very quick to build.

ToDo here
---------

* example apps and tutorials
* links into API documentation
