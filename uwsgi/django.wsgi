# Generic WSGI application
import os
from django.core.wsgi import get_wsgi_application

def application(environ, start):

    for key in os.environ:
        print("os environ %s = %s" % (key, os.environ[key]))

    # copy any vars into os.environ
    for key in environ:
        print("app environ [%s] = [%s]" % (key, environ[key]))
        os.environ[key] = str(environ[key])
        print("new os environ [%s] = [%s]", (key, os.environ[key]))

    return get_wsgi_application()(environ,start)
