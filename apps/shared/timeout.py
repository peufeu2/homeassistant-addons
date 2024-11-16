#!/usr/bin/python
# -*- coding: utf-8 -*-

import appdaemon.plugins.hass.hassapi as hassapi
import time, asyncio

MODULE_VERSION = 23

"""
    Calls the callback at the end of the timeout.
    Timeout can be cancelled, prolonged, shortened.

    It has 2 states:
    - Expired:  timer=None, callback will not trigger
    - Running:  timer valid, callback will trigger

    expiry contains the expiration time (when the callback will be called).
    It is not reset when the timeout is expired or cancelled.

"""
class DelayedCallback:
    def __init__( self, api, callback ):
        self.api = api
        self.callback = callback
        self.timer = None       # If timer is not None, the timer is running and will trigger the callback
        self.expiry = 0         # Expiry is zero when canceled.
        self.start_time = None  # Used to know for how long the timeout has been running. 
        api.log("DelayedCallback V%s", MODULE_VERSION)

    """
        True if the timeout's callback will trigger in the future.
        False if cancelled or paused.
    """
    def running( self ):
        return bool( self.timer )

    """
        Remaining time in seconds.
        0 if cancelled or expired.
    """
    def remaining( self ):
        return max(0, self.expiry - time.monotonic())

    """
        Time elapsed since the start of the timeout, in seconds.
    """
    def elapsed( self ):
        return time.monotonic() - self.start_time

    """
        Start or prolong the timeout, ensuring it will expire *at least* in "duration" seconds.
        Returns the amount of time remaining.
    """
    def at_least( self, duration ):
        return self.expire_at( max( self.expiry, time.monotonic() + duration ))

    """
        Shortens the timeout, ensuring it will expire *at most* in "duration" seconds.
        Returns the amount of time remaining.
    """
    def at_most( self, duration ):
        expiry = time.monotonic() + duration
        if self.timer:
            # If timeout was running, and more time remains than duration parameter, shorten it .
            return self.expire_at( min( self.expiry, expiry ))
        else:
            # If timeout was not running, start it with duration parameter.
            return self.expire_at( expiry )

    """
        If timeout is not active, start it with the specified duration.
        If it was already running, adjust the duration.
        Returns the amount of time remaining.
    """
    def set( self, duration ):
        return self.expire_at( time.monotonic() + duration )

    """
        If timeout is not active, start it with the specified expiry time.
        If it was already running:
            ... with a different expiry time, cancel it and restart it with the new expiry.
            ... with the same expiry time, just let it run.
        Returns the amount of time remaining.
    """
    def expire_at( self, expiry ):
        t = time.monotonic()
        if self.timer:                      # timeout is active
            if self.expiry == expiry:       # no change in expiry time: just return
                return expiry - t
            self.cancel()                   # cancel timeout to change the expiry
        else:
            self.start_time = t             # set start_time only of we do not modify a running timeout
        duration = expiry - t
        if duration <= 0:                   # expiry is in the past, don't bother with the timer
            self.api.log("direct callback %s", duration)
            self.callback()
            return 0
        else:
            self.api.log("timer set to %s", duration)
            self.expiry = expiry
            self.timer = self.api.run_in( self._timer_callback, duration )
            return duration

    """
        Cancels the timeout.
        Does not call the callback.
    """
    def cancel( self ):
        self.api.log("cancel timer %s", self.timer)
        if self.timer:
            self.api.cancel_timer( self.timer )
            self.timer = None

    """
        Forget the expiry time so this timeout can no longer be extended
    """
    def reset( self ):
        self.cancel()
        self.expiry = 0

    """
        Called by the API timer when the timeout expires.
    """
    def _timer_callback( self, kwargs ):
        self.timer = None
        self.callback()


"""
Timer to control a light (or anything else).
"""
class StateTimer:
    def __init__( self, api, name, callback ):
        self.api = api
        self.name = name
        self.callback = callback
        self.timer = None       # If timer is not None, the timer is running and will trigger the callback
        self.expiry = 0         # Expiry is zero when canceled.
        self.start_time = None  # Used to know for how long the timeout has been running. 
        self.state = None
        api.log("LightTimer %s V%s", self.name, MODULE_VERSION)

    """
    If duration is None: turn on permanently. Otherwise,
    If OFF, turn ON with the specified duration.
    If ON, adjust the duration.
    Returns the amount of time remaining."""
    def turn_on( self, duration=None ):
        if not duration:
            self._set_state( True )
        else:
            return self.expire_at( time.monotonic() + duration )

    """
    Start or prolong the ON time, ensuring it will turn off  *at least* after  "duration" seconds.
    Returns the amount of time remaining."""
    def at_least( self, duration ):
        return self.expire_at( max( self.expiry, time.monotonic() + duration ))

    """
    Shortens the ON time, ensuring it will expire *at most* in "duration" seconds.
    Returns the amount of time remaining."""
    def at_most( self, duration ):
        expiry = time.monotonic() + duration
        if self.timer:
            # If timeout was running, and more time remains than duration parameter, shorten it .
            return self.expire_at( min( self.expiry, expiry ))
        else:
            # If timeout was not running, start it with duration parameter.
            return self.expire_at( expiry )

    """
    Cancel the timeout and sets state to OFF."""
    def turn_off( self, kwargs=None ):
        self.cancel()
        self._set_state( False )

    """
    If OFF, turn ON the specified expiry time.
    If ON, adjust expiry time.
    Returns the amount of time remaining."""
    def expire_at( self, expiry ):
        t = time.monotonic()
        duration = expiry - t
        self.api.log("%s: expire_at %s s", self.name, duration)
        if self.timer:                      # timeout is active
            if self.expiry == expiry:       # no change in expiry time: just return
                self._set_state( True )
                return expiry - t
            self.cancel()                   # cancel timeout to change the expiry
        else:
            self.start_time = t             # set start_time only of we do not modify a running timeout
        if duration <= 0:                   # expiry is in the past, don't bother with the timer
            self.api.log("%s: negative duration %s", self.name, duration)
            self._set_state( False )
            return 0
        else:
            self.api.log("%s: timer set to %s", self.name, duration)
            self.expiry = expiry
            self.timer = self.api.run_in( self._timer_callback, duration )
            self._set_state( True )
            return duration

    """
    Cancels the timeout.
    Does not call the callback."""
    def cancel( self ):
        self.api.log("%s: cancel timer %s", self.name, self.timer)
        if self.timer:
            self.api.cancel_timer( self.timer )
            self.timer = None

    "at timer expiration"
    def _timer_callback( self, kwargs ):
        self.timer = None
        self._set_state( False )

    "sets the state and triggers the callback"
    def _set_state( self, state ):
        if state != self.state:
            self.api.log("%s: set state %s", self.name, state)
            self.state = state
            self.callback( self, state )