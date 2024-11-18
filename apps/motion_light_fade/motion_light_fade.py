import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib
import grug_timeout
# importlib.reload( shared.timeout )

"""
    Motion activated light with fade out

    sensors:        A list of motion sensors, as HA entities.
    light:          Light entity to control.

    set log_level DEBUG in this app's yaml config for logging.
"""
class MotionLightFadeActor:
    def __init__( self, api, args ):
        self.api    = api
        self.name   = args[ "name" ]
        self.light  = args[ "light" ]
        self.fade_list = args[ "fade" ]

        self.timer = grug_timeout.DelayedCallback( api, self.light_off )
        self.sensor_state = {}
        self.sensors = args["sensors"]
        for sensor in self.sensors:
            api.listen_state( self.on_sensor, sensor )  # motion detector

        # If the light is on at app startup, remember to turn it off.        
        if self.api.get_state( self.light ) == "on":
            self.start_countdown()

    def cancel(self):
        self.timer.cancel()

    def do_fade( self, fade ):
        if fade["brightness"]:
            self.debug("fade: %s", fade)
            self.api.turn_on( self.light, brightness=fade["brightness"], transition=fade["fade_time"] )
        else:
            self.debug("light off")
            self.api.turn_off( self.light, transition=fade["fade_time"] )

    "Turn the light on"
    def light_on( self ):
        self.debug( "light_on" )
        self.do_fade( self.fade_list[0] )
    
    def start_countdown( self ):
        self.fade_iter = iter( self.fade_list[1:] )
        self.timer.set( self.fade_list[0]["wait_time"] )

    "Proceed to the list of brightness and wait times"
    def light_off( self ):
        for fade in self.fade_iter:
            self.do_fade( fade )
            self.timer.set( fade["wait_time"] )
            return

    """Motion sensor state change
    """
    def on_sensor( self, entity, attribute, old, new, kwargs ):

        #   Any sensor state change to "occupancy on" will turn on the lights
        if new == "on":              # presence detected
            self.light_on()
            self.start_countdown()

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )

#   Using separate class here, to avoid conflicts between hassapi.Hass
#   member functions and variable and our own class stuff.
#
class MotionLightFade(hassapi.Hass):
    def initialize(self):
        self.depends_on_module( grug_timeout )
        self.__actor = MotionLightFadeActor( self, self.args )

    def cancel(self):
        self.__actor.cancel()


