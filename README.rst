================
Comet IRC Viewer
================
:Info: A web-based IRC viewer.
:Author: Harry Marr (http://github.com/hmarr)

About
=====
A simple web interface for viewing IRC conversations. At the moment it's
limited to one channel at a time. Twisted is used to serve up the front-end and
JSON updates. The IRC bot runs in the same event loop.

Usage
=====
    Usage: ircviewer.py [options] irc_host[:port] channel

    Options:
      -h, --help            show this help message and exit
      -p PORT, --port=PORT  Port to run the HTTP server on
      -n NICK, --nick=NICK  IRC bot nickname
      -a AUTH, --auth=AUTH  Authentication (user:password)

