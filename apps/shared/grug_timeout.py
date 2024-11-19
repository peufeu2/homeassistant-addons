#!/usr/bin/python
# -*- coding: utf-8 -*-

import appdaemon.plugins.hass.hassapi as hassapi
import time, asyncio, datetime, json

import grug_persist

MODULE_VERSION = 32

"""
    Calls the callback at the end of the timeout.
    Timeout can be cancelled, prolonged, shortened.

    It has 2 states:
    - Expired:  timer=None, callback will not trigger
    - Running:  timer valid, callback will trigger

    expiry contains the expiration time (when the callback will be called).
    It is not reset when the timeout is expired or cancelled.

"""
class DelayedCallbackF:
    def __init__( self, api, callback ):
        self.api = api
        api.depends_on_module( grug_persist )
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
            self.debug("DelayedCallback.expire_at: Direct callback %s", duration)
            self.callback()
            return 0
        else:
            self.debug("DelayedCallback.expire_at: Timer set to %s", duration)
            self.expiry = expiry
            self.timer = self.api.run_in( self._timer_callback, duration )
            return duration

    """
        Cancels the timeout.
        Does not call the callback.
    """
    def cancel( self ):
        self.debug("DelayedCallback: Cancel timer %s", self.timer)
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
    
    def debug( self, fmt, *args ):
        self.debug( fmt, *args, level="DEBUG" )

"""
    Same as DelayedCallbackF, with all times stored in UTC.
    This is to save it to a file and reload it after reboot, 
    can't do that with time.monotonic()
"""
class DelayedCallback( grug_persist.PersistMixin ):
    def __init__( self, api, callback, entity_storage_id = None ):
        self.api = api
        self.callback = callback
        self.timer = None       # If timer is not None, the timer is running and will trigger the callback
        self.expiry = None      # Expiry is None when canceled.
        self.start_ts = None  # Used to know for how long the timeout has been running. 
        self.entity_storage_id = entity_storage_id
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
        if self.expiry:
            return (self.expiry - self.api.get_now()).total_seconds()
        else:
            return 0

    """
        Time elapsed since the start of the timeout, in seconds.
    """
    def elapsed( self ):
        if self.start_ts:
            return (self.api.get_now() - self.start_ts).total_seconds()
        else:
            return None

    """
        Start or prolong the timeout, ensuring it will expire *at least* in "duration" seconds.
        Returns the amount of time remaining.
    """
    def at_least( self, duration ):
        expiry = self.api.get_now() + datetime.timedelta(seconds=duration)
        if self.expiry and self.expiry > expiry:
            return self.expire_at( self.expiry )
        else:
            return self.expire_at( expiry )

    """
        Shortens the timeout, ensuring it will expire *at most* in "duration" seconds.
        Returns the amount of time remaining.
    """
    def at_most( self, duration ):
        expiry = self.api.get_now() + datetime.timedelta(seconds=duration)
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
        return self.expire_at( self.api.get_now() + datetime.timedelta(seconds=duration) )

    """
        If timeout is not active, start it with the specified expiry time.
        If it was already running:
            ... with a different expiry time, cancel it and restart it with the new expiry.
            ... with the same expiry time, just let it run.
        Returns the amount of time remaining.
    """
    def expire_at( self, expiry ):
        now = self.api.get_now()
        if self.timer:                      # timeout is active
            if self.expiry == expiry:       # no change in expiry time: just return
                return (expiry - now).total_seconds()
            self.cancel()                   # cancel timeout to change the expiry
        else:
            self.start_ts = now             # set start_ts only of we do not modify a running timeout
        duration = (expiry - now).total_seconds()
        if expiry <= now:                   # expiry is in the past, don't bother with the timer
            self.debug("DelayedCallback.expire_at: Direct callback %s", duration)
            self.callback()
            return 0
        else:
            self.debug("DelayedCallback.expire_at: Timer set to %s", duration)
            self.expiry = expiry
            self.timer = self.api.run_at( self._timer_callback, expiry )
            self.save()
            return duration

    """
        Cancels the timeout.
        Does not call the callback.
    """
    def cancel( self ):
        self.debug("DelayedCallback: Cancel timer %s", self.timer)
        if self.timer:
            self.api.cancel_timer( self.timer )
            self.timer = None
            self.save()

    """
        Forget the expiry time so this timeout can no longer be extended
    """
    def reset( self ):
        self.cancel()
        self.expiry = None
        self.save()

    """
        Called by the API timer when the timeout expires.
    """
    def _timer_callback( self, kwargs ):
        self.timer = None
        self.save()
        self.callback()
    
    def debug( self, fmt, *args ):
        self.debug( fmt, *args, level="DEBUG" )
    
    def save( self ):
        state = "on" if self.timer else "off"
        attrs = { k:getattr( self, k ) for k in ("start_ts", "expiry") }
        self._save( state, attrs )

    def load( self ):
        state, attrs = self._load()
        if state == None:
            return self.reset()
        else:
            self.start_ts = attrs["start_ts"]
            self.expiry   = attrs["expiry"]
            if state == "on":
                self.expire_at( self.expiry )

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )


# """
# Timer to control a light (or anything else).
# """
# class StateTimer:
#     def __init__( self, api, name, callback ):
#         self.api = api
#         self.name = name
#         self.callback = callback
#         self.timer = None       # If timer is not None, the timer is running and will trigger the callback
#         self.expiry = 0         # Expiry is zero when canceled.
#         self.start_time = None  # Used to know for how long the timeout has been running. 
#         self.state = None
#         api.log("LightTimer %s V%s", self.name, MODULE_VERSION)

#     """
#     If duration is None: turn on permanently. Otherwise,
#     If OFF, turn ON with the specified duration.
#     If ON, adjust the duration.
#     Returns the amount of time remaining."""
#     def turn_on( self, duration=None ):
#         if not duration:
#             self._set_state( True )
#         else:
#             return self.expire_at( time.monotonic() + duration )

#     """
#     Start or prolong the ON time, ensuring it will turn off  *at least* after  "duration" seconds.
#     Returns the amount of time remaining."""
#     def at_least( self, duration ):
#         return self.expire_at( max( self.expiry, time.monotonic() + duration ))

#     """
#     Shortens the ON time, ensuring it will expire *at most* in "duration" seconds.
#     Returns the amount of time remaining."""
#     def at_most( self, duration ):
#         expiry = time.monotonic() + duration
#         if self.timer:
#             # If timeout was running, and more time remains than duration parameter, shorten it .
#             return self.expire_at( min( self.expiry, expiry ))
#         else:
#             # If timeout was not running, start it with duration parameter.
#             return self.expire_at( expiry )

#     """
#     Cancel the timeout and sets state to OFF."""
#     def turn_off( self, kwargs=None ):
#         self.cancel()
#         self._set_state( False )

#     """
#     If OFF, turn ON the specified expiry time.
#     If ON, adjust expiry time.
#     Returns the amount of time remaining."""
#     def expire_at( self, expiry ):
#         t = time.monotonic()
#         duration = expiry - t
#         self.debug("%s: expire_at %s s", self.name, duration)
#         if self.timer:                      # timeout is active
#             if self.expiry == expiry:       # no change in expiry time: just return
#                 self._set_state( True )
#                 return expiry - t
#             self.cancel()                   # cancel timeout to change the expiry
#         else:
#             self.start_time = t             # set start_time only of we do not modify a running timeout
#         if duration <= 0:                   # expiry is in the past, don't bother with the timer
#             self.debug("%s: negative duration %s", self.name, duration)
#             self._set_state( False )
#             return 0
#         else:
#             self.debug("%s: timer set to %s", self.name, duration)
#             self.expiry = expiry
#             self.timer = self.api.run_in( self._timer_callback, duration )
#             self._set_state( True )
#             return duration

#     """
#     Cancels the timeout.
#     Does not call the callback."""
#     def cancel( self ):
#         self.debug("%s: cancel timer %s", self.name, self.timer)
#         if self.timer:
#             self.api.cancel_timer( self.timer )
#             self.timer = None

#     "at timer expiration"
#     def _timer_callback( self, kwargs ):
#         self.timer = None
#         self._set_state( False )

#     "sets the state and triggers the callback"
#     def _set_state( self, state ):
#         if state != self.state:
#             self.debug("%s: set state %s", self.name, state)
#             self.state = state
#             self.callback( self, state )