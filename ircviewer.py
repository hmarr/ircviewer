#!/usr/bin/env python

import sys
try:
    import json
except ImportError:
    import simplejson as json
from optparse import OptionParser
import time
import logging

from twisted.words.protocols import irc
from twisted.internet import protocol, reactor
from twisted.web.server import Site
from twisted.web import server, http
from twisted.web.resource import Resource
from twisted.web.static import File
from twisted.web.error import NoResource

auth_user = auth_password = None

def setup_logger(logger):
    console_handler = logging.StreamHandler()
    format = "[%(levelname)s] - %(asctime)s - %(message)s"
    console_handler.setFormatter(logging.Formatter(format))
    logger.addHandler(console_handler)


class LogBot(irc.IRCClient):
    """IRC bot that sends updates to the web handler.
    """

    def _get_nickname(self):
        return self.factory.nickname

    nickname = property(_get_nickname)

    def signedOn(self):
        self.join(self.factory.channel)
        logger.info("Connected to server as %s" % self.nickname)

    def joined(self, channel):
        logger.info("Joined channel %s" % channel)

    def privmsg(self, user, channel, message):
        logger.info("Message from %s: %s" % (user.split('!')[0], message))

        action = {
            'command': 'privmsg',
            'user': user,
            'message': message,
            'timestamp': int(time.time()),
        }
        self.factory.add_to_history(action)
        self.factory.web_resource.update(action)

    def userJoined(self, user, channel):
        logger.info("%s joined" % user.split('!')[0])

        action = {
            'command': 'userjoined',
            'user': user,
            'timestamp': int(time.time()),
        }
        self.factory.add_to_history(action)
        self.factory.web_resource.update(action)

    def userLeft(self, user, channel):
        logger.info("%s left" % user.split('!')[0])

        action = {
            'command': 'userleft',
            'user': user,
            'timestamp': int(time.time()),
        }
        self.factory.add_to_history(action)
        self.factory.web_resource.update(action)

    def userQuit(self, user, message):
        logger.info("%s quit" % user.split('!')[0])

        action = {
            'command': 'userquit',
            'user': user,
            'timestamp': int(time.time()),
        }
        self.factory.add_to_history(action)
        self.factory.web_resource.update(action)


class LogBotFactory(protocol.ClientFactory):

    protocol = LogBot

    def __init__(self, channel, web_resource, nickname='LogBot', 
                 history_file='irc-history.log', history_cache_size=500):
        self.channel = channel
        self.web_resource = web_resource
        self.nickname = nickname
        self.history_file = history_file
        self.history_cache_size = history_cache_size
        self.history = self.load_history()

    def load_history(self):
        """Load history from a JSON history file, where each line should be
        valid JSON and correspond to a single action.
        """
        history = []
        try:
            for line in open(self.history_file):
                history.append(line)
                # Ensure that we're not loading more than is necessary
                if len(history) > self.history_cache_size:
                    history.pop(0)
            # Convert the JSON strings to actions (dicts)
            history = [json.loads(line) for line in history]
        except:
            pass
        return history

    def add_to_history(self, action):
        """Add an item to the history, this will also be saved to disk.
        """
        self.history.append(action)
        while len(self.history) > self.history_cache_size:
            self.history.pop(0)
        open(self.history_file, 'a').write(json.dumps(action) + '\n')

    def clientConnectionLost(self, connector, reason):
        logger.warn("Lost connection (%s)" % reason.getErrorMessage())
        logger.warn("Reconnecting to server...")
        connector.connect()

    def clientConnectionFailed(self, connector, reason):
        logger.error("Could not connect (%s)" % reason.getErrorMessage())
        sys.exit(1)


def escape_html(text):
    """Produce entities within text."""
    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }
    return "".join(html_escape_table.get(c,c) for c in text)

def authenticate(func):
    """Decorator to restrict access to pages to authenticated clients.
    """
    def auth_func(self, request, *args, **kwargs):
        user = request.getUser()
        password = request.getPassword()
        if auth_user and auth_password:
            if user != auth_user or password != auth_password:
                request.setResponseCode(http.UNAUTHORIZED)
                realm = 'basic realm="IRC Viewer"'
                request.setHeader('WWW-authenticate', realm)
                return ''
        return func(self, request, *args, **kwargs)
    return auth_func


def prepare_action(action):
    """Prepare an action for sending to the client - escape quotes, etc.
    """
    action = action.copy()
    # Select only the *name* part of the user's name
    if 'user' in action:
        action['user'] = action['user'].split('!')[0]

    for key, value in action.items():
        if isinstance(key, basestring):
            key = escape_html(key)
        if isinstance(value, basestring):
            value = escape_html(value)
        action[key] = value
    return action


class IrcLogUpdate(Resource):
    """A Twisted web resource that uses long-polling to send IRC updates to
    clients as JSON.
    """

    isLeaf = True

    def __init__(self):
        self.clients = []
        Resource.__init__(self)

    @authenticate
    def render_GET(self, request):
        request.setHeader('Content-Type', 'application/json')
        # Add the client to the client list; the response will be returned when
        # a new action occurs
        self.clients.append(request)
        request.notifyFinish().addErrback(self.lost_client, request)
        return server.NOT_DONE_YET
    
    def lost_client(self, err, client):
        """Remove the client in the event of a disconnect or error.
        """
        if client in self.clients:
            self.clients.remove(client)
    
    def update(self, action):
        """Update all waiting clients with a new action.
        """
        payload = json.dumps(prepare_action(action))

        clients = self.clients[:]
        self.clients = []
        for client in clients:
            client.write(payload)
            client.finish()


class IrcLogHistory(Resource):
    """A Twisted web resource that returns IRC history as JSON.
    """

    isLeaf = True

    def __init__(self, log_bot_factory):
        self.log_bot_factory = log_bot_factory

    @authenticate
    def render_GET(self, request):
        request.setHeader('Content-Type', 'application/json')

        history = []
        for action in self.log_bot_factory.history:
            history.append(prepare_action(action))

        return json.dumps(history)


# Set up logging
logger = logging.getLogger('ircviewer')
setup_logger(logger)

def main():
    usage = 'usage: %prog [options] irc_host[:port] channel'
    parser = OptionParser(usage)
    parser.add_option('-p', '--port', help='Port to run the HTTP server on', 
                      default=8080, type='int')
    parser.add_option('-n', '--nick', help='IRC bot nickname', type='str',
                      default='IRCViewer')
    parser.add_option('-a', '--auth', help='Authentication (user:password)', 
                      type='str')
    options, args = parser.parse_args()

    # Parse the connection string with format host[:port]
    try:
        irc_host, irc_port = args[0], 6667
        if ':' in irc_host:
            irc_host, irc_port = args[0].split(':')
            irc_port = int(irc_port)
    except:
        parser.error('invalid IRC host/port, use format hostname[:port]')

    # Ensure the channel is present
    try:
        channel = '#' + args[1].strip('#')
    except:
        parser.error('invalid or missing IRC channel')

    # Set up authentication details if provided
    if options.auth is not None:
        if len(options.auth.split(':')) != 2:
            parser.error("invalid auth details, use format user:password")

        auth_user, auth_password = options.auth.split(':')
        if not auth_user or not auth_password:
            parser.error("invalid auth details, use format user:password")

    logger.setLevel(logging.INFO)

    # Set up the web resources for displaying the logs
    web_resource = Resource()

    update_web_resource = IrcLogUpdate()
    web_resource.putChild("", File('main.html'))
    web_resource.putChild("update.js", update_web_resource)
    web_resource.putChild("static", File("static"))

    web_factory = Site(web_resource)
    reactor.listenTCP(options.port, web_factory)

    log_bot_factory = LogBotFactory(channel, update_web_resource, 
                                    nickname=options.nick)
    reactor.connectTCP(irc_host, irc_port, log_bot_factory)

    web_resource.putChild("history.js", IrcLogHistory(log_bot_factory))

    logger.info('Starting HTTP server on port %d' % options.port)
    reactor.run()

if __name__ == '__main__':
    main()
