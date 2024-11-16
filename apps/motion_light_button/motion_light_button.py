import appdaemon.plugins.hass.hassapi as hassapi
import time

# Args:
# sensor: binary sensor to use as trigger
# light : entity to turn on when detecting motion
# delay: amount of time after turning on to turn off again. If not specified defaults to 60 seconds.
#

class MotionLightButtonActor:
    def __init__( self, api, name, sensor, light, delay, button_delay, **kwargs ):
        self.api    = api
        self.name   = name
        self.timer  = None
        self.light  = light
        self.delay  = delay
        self.button_delay   = button_delay
        self.expiry = 0
        self.light_state_set = None
        
        api.listen_state( self.on_sensor, sensor )
        api.listen_state( self.on_light, light )
        api.log( "initialize %s" % kwargs )

    def cancel(self):
        self.cancel_timer()
    
    def cancel_timer( self ):
        api = self.api
        if self.timer:
            api.cancel_timer( self.timer )
            self.timer = None
    
    def set_timer( self, delay ):
        api = self.api
        self.cancel_timer()
        t = time.monotonic()
        self.expiry = max( self.expiry, t+delay )
        delay = self.expiry-t
        api.log( "set_timer %s", delay )
        self.timer = api.run_in( self.light_off, delay )

    def light_off( self, kwargs ):
        api = self.api
        api.log( "light_off" )
        self.timer = None
        self.light_state_set = "off"      # used in on_light()
        api.turn_off( self.light )
    
    # sensor state change
    def on_sensor( self, entity, attribute, old, new, kwargs ):
        api = self.api
        api.log( "on_sensor(%s -> %s)" % (old, new) )
        if new == "on":
            self.cancel_timer()           # no countdown when sensor detects
            self.light_state_set = "on"   # used in on_light()
            api.log( "light_on" )
            api.turn_on( self.light )
        elif api.get_state( self.light ) == "on":
            self.set_timer( self.delay )  # begin countdown

    # relay state change
    def on_light( self, entity, attribute, old, new, kwargs ):
        api = self.api
        if new != self.light_state_set:
            # triggered by button wired directly to relay (relay is retarded and does not report button state, only its own state)
            self.light_state_set = None
            api.log( "on_light(%s -> %s)" % (old, new) )
            if new == "on":
                # light turned on by button
                self.set_timer( self.button_delay )
            else:
                # light turned off by button
                self.expiry = 0
                self.cancel_timer()

class MotionLightButton(hassapi.Hass):
    def initialize(self):
        self.__actor = MotionLightButtonActor( self, **self.args )

    def cancel(self):
        self.__actor.cancel()
