import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib

import grug_timeout, grug_persist
# importlib.reload( shared.timeout )

"""
    Motion activated light with fade out

    sensors:        A list of motion sensors, as HA entities.
    light:          Light entity to control.

    set log_level DEBUG in this app's yaml config for logging.
"""
class MotionLightFadeActor( grug_persist.PersistMixin ):
    def __init__( self, api, args ):
        self.api    = api
        self.name   = args[ "name" ]
        self.light  = args[ "light" ]
        self.fade_list = args[ "fade" ]
        self.step = len(self.fade_list)-1
        self.timer = grug_timeout.DelayedCallback( api, self.light_off, self.name+".timer" )

        self.sensor_state = {}
        self.sensors = args["sensors"]
        for sensor in self.sensors:
            api.listen_state( self.on_sensor, sensor )  # motion detector

        # Load first, it will set timer to default value
        self.entity_storage_id   = self.name + ".storage"
        self.load()

        # ... then load the saved timer expiration
        self.timer.load()

    def cancel( self ):
        self.timer.cancel()

    def reset( self ):
        self.timer.cancel()
        self.api.turn_off( self.light )

    def do_fade( self, step ):
        fade = self.fade_list[step]
        if fade["brightness"]:
            self.debug("fade: %s", fade)
            self.api.turn_on( self.light, brightness=fade["brightness"], transition=fade["fade_time"] )
        else:
            self.debug("light off")
            self.api.turn_off( self.light, transition=fade["fade_time"] )
        self.step = step
        self.save()

    "Turn the light on"
    def light_on( self, step=0 ):
        self.debug( "################################## light_on" )
        step = min(max(0,step), len(self.fade_list)-1)
        self.fade_iter = iter(range( step+1, len( self.fade_list )))
        self.timer.set( self.fade_list[step]["wait_time"] )
        self.do_fade( step )

    "Proceed to the list of brightness and wait times"
    def light_off( self ):
        for step in self.fade_iter:
            self.debug( "Fade step %d", step )
            self.timer.set( self.fade_list[step]["wait_time"] )
            self.do_fade( step )
            return

    """Motion sensor state change
    """
    def on_sensor( self, entity, attribute, old, new, kwargs ):
        #   Any sensor state change to "occupancy on" will turn on the lights
        if new == "on":              # presence detected
            self.light_on()

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )

    def save( self ):
        state = "on" if self.step < len(self.fade_list)-1 else "off"
        attrs = { k:getattr( self, k ) for k in ("step", ) }
        self._save( state, attrs )

    def load( self ):
        state, attrs = self._load()
        if state == None or state == "off":
            return self.reset()
        else:
            step = attrs["step"]
            if state == "on":
                self.light_on( step )

#   Using separate class here, to avoid conflicts between hassapi.Hass
#   member functions and variable and our own class stuff.
#
class MotionLightFade(hassapi.Hass):
    def initialize(self):
        self.depends_on_module( grug_timeout )
        self.depends_on_module( grug_persist )
        self.__actor = MotionLightFadeActor( self, self.args )

    def cancel(self):
        self.__actor.cancel()


