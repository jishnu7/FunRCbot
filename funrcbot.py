#!/usr/bin/env python

'''
A Python IRC bot.

Starting point -> http://www.habnabit.org/twistedex.html
'''
import sys
import os
import random
from twisted.internet import reactor
from twisted.internet import defer
from twisted.internet import protocol
from twisted.python import log
from twisted.words.protocols import irc
from twisted.application import internet, service
import config

__author__ = "Jishnu Mohan"
__copyright__ = "Copyright 2012, Jishnu Mohan <jishnu7@gmail.com>"
__license__ = "GPL"
__email__ = "jishnu7@gmail.com"


class FunRCProtocol(irc.IRCClient):
    nickname = config.NICK

    def __init__(self, *args, **kwargs):
        self._namescallback = {}

    def signedOn(self):
        # This is called once the server has acknowledged that we sent
        # both NICK and USER.
        for channel in self.factory.channels:
            self.join(channel)

    # Obviously, called when a PRIVMSG is received.
    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        message = message.strip()
        if not message.startswith('!'):
            # not a trigger command
            # do nothing
            return
        command, sep, rest = message.lstrip('!').partition(' ')
        # Get the function corresponding to the command given.
        func = getattr(self, 'command_' + command, None)
        # Or, if there was no function, ignore the message.
        if func is None:
            return
        # maybeDeferred will always return a Deferred. It calls func(rest), and
        # if that returned a Deferred, return that. Otherwise, return the return
        # value of the function wrapped in twisted.internet.defer.succeed. If
        # an exception was raised, wrap the traceback in
        # twisted.internet.defer.fail and return that.
        d = defer.maybeDeferred(func, rest)
        # Add callbacks to deal with whatever the command results are.
        # If the command gives error, the _show_error callback will turn the
        # error into a terse message first:
        d.addErrback(self._show_error)
        # Whatever is returned is sent back as a reply:
        if channel == self.nickname:
            # When channel == self.nickname, the message was sent to the bot
            # directly and not to a channel. So we will answer directly too:
            d.addCallback(self._send_message, nick)
        else:
            # Otherwise, send the answer to the channel, and use the nick
            # as addressing in the message itself:
            d.addCallback(self._send_message, channel, nick)

    def _send_message(self, msg, target, nick=None):
        if nick:
            msg = '%s, %s' % (nick, msg)
        self.msg(target, msg)

    def _show_error(self, failure):
        return failure.getErrorMessage()

    def command_ping(self, rest):
        return 'Pong.'

    def command_hi(self, rest):
        return 'Hello.'

    def command_saylater(self, rest):
        when, sep, msg = rest.partition(' ')
        when = int(when)
        d = defer.Deferred()
        # A small example of how to defer the reply from a command. callLater
        # will callback the Deferred with the reply after so many seconds.
        reactor.callLater(when, d.callback, msg)
        # Returning the Deferred here means that it'll be returned from
        # maybeDeferred in privmsg.
        return d

    def got_names(self, nicklist):
        log.msg(nicklist)
        remove = config.BOTS
        nicklist = [item for item in nicklist if item not in remove]

        return "selected " + random.choice(list(nicklist)) \
            + " to make tea"

    def command_maketea(self, rest):
        return self.names(config.CHANNEL).addCallback(self.got_names)

    def command_fortune(self, rest):
        return os.popen('fortune -s').read().translate(None, '\n\r\t')

    def names(self, channel):
        channel = channel.lower()
        d = defer.Deferred()
        if channel not in self._namescallback:
            self._namescallback[channel] = ([], [])

        self._namescallback[channel][0].append(d)
        self.sendLine("NAMES %s" % channel)
        return d

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2].lower()
        nicklist = params[3].split(' ')
        if channel not in self._namescallback:
            return
        n = self._namescallback[channel][1]
        n += nicklist

    def irc_RPL_ENDOFNAMES(self, prefix, params):
        channel = params[1].lower()
        if channel not in self._namescallback:
            return
        callbacks, namelist = self._namescallback[channel]
        for cb in callbacks:
            cb.callback(namelist)
        del self._namescallback[channel]


class FunRCFactory(protocol.ReconnectingClientFactory):
    protocol = FunRCProtocol
    channels = [config.CHANNEL]

if __name__ == '__main__':
    # This runs the program in the foreground. We tell the reactor to connect
    # over TCP using a given factory, and once the reactor is started, it will
    # open that connection.
    reactor.connectTCP(config.HOST, config.PORT, FunRCFactory())
    # Since we're running in the foreground anyway, show what's happening by
    # logging to stdout.
    log.startLogging(sys.stdout)
    # And this starts the reactor running. This call blocks until everything is
    # done, because this runs the whole twisted mainloop.
    reactor.run()

# This runs the program in the background. __name__ is __builtin__ when you use
# twistd -y on a python module.
elif __name__ == '__builtin__':
    # Create a new application to which we can attach our services. twistd wants
    # an application object, which is how it knows what services should be
    # running. This simplifies startup and shutdown.
    application = service.Application('FunRCBot')
    # twisted.application.internet.TCPClient is how to make a TCP client service
    # which we can attach to the application.
    ircService = internet.TCPClient(config.HOST, config.PORT, FunRCFactory())
    ircService.setServiceParent(application)
    # twistd -y looks for a global variable in this module named 'application'.
    # Since there is one now, and it's all set up, there's nothing left to do.
