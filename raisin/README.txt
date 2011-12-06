===============================
Get Started Quickly With Raisin
===============================

Check out the buildout from SVN using the rnaguest user::

  $ svn co --username rnaguest --password rnaguest svn://svn.crg.es/big/raisin/raisin.buildout/trunk raisin.buildout
  $ cd raisin.buildout

Create a virtual environment and run the buildout::

  $ /path/to/your/python/bin/virtualenv --no-site-packages .
  $ bin/python bootstrap.py
  $ bin/buildout

Raisin is now built and ready to run.

It expects a MySQL server with the following configuration:

  [raisin]
  port = 3306
  server = 127.0.0.1
  user = raisin
  password = raisin

You can change these settings in etc/connections/development.ini if necessary.

Run the Restish instance of Raisin using the Paste HTTP server in the foreground::

  $ bin/paster serve etc/restish/development.ini

Get a resource from the restish server::

  $ curl -i -H "Accept:text/csv" 127.0.0.1:6464/projects

Run the Pyramid instance of Raisin using the Paste HTTP server in the foreground::

  $ bin/paster serve etc/pyramid/development.ini

Visit the Pyramid test instance of Raisin at::

  http://localhost:7777/

Default login and password are admin/admin.
  
Enjoy!
