import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib
import grug_timeout
# importlib.reload( shared.timeout )


# Args:
# sensor: binary sensor to use as trigger
# light : entity to turn on when detecting motion
# delay: amount of time after turning on to turn off again. If not specified defaults to 60 seconds.
#
class MotionLightButtonActor:
    def __init__( self, api, name, sensors, light, motion_delay, button_delay, **kwargs ):
        self.api    = api
        self.name   = name
        self.light  = light
        self.motion_delay = motion_delay
        self.button_delay = button_delay

        self.timer = grug_timeout.DelayedCallback( api, self.light_off )
        self.light_state_we_set = None # remember if it was us who set the light
        
        self.sensor_state = {}
        self.sensors = sensors
        for sensor in sensors:
            api.listen_state( self.on_sensor, sensor )  # motion detector
        api.listen_state( self.on_light, light )    # relay state change from wired button

    def cancel(self):
        self.timer.cancel()
    
    def light_off( self ):
        self.debug( "light_off" )
        self.light_state_we_set = "off"
        self.api.turn_off( self.light )

    def light_on( self ):
        self.debug( "light_on" )
        self.light_state_we_set = "on"
        self.api.turn_on( self.light )
    
    # sensor state change
    def on_sensor( self, entity, attribute, old, new, kwargs ):
        self.debug( "on_sensor %s (%s -> %s)", entity, old, new )
        old_states = [ self.sensor_state.get(id) for id in self.sensors ]
        self.sensor_state[ entity ] = new
        new_states = [ self.sensor_state.get(id) for id in self.sensors ]
        self.debug( "%s -> %s" , old_states, new_states )
        if new == "on":                                 # presence detected
            self.timer.cancel()                  # stop countdown when sensor detects motion
            self.light_on()
        elif "on" not in new_states and self.api.get_state( self.light ) == "on":       # no presence detected and light is on
            # Begin countdown. This will not shorten the timeout set by the button.
            self.timer.at_least( self.motion_delay )

    # relay state change from pushbutton
    def on_light( self, entity, attribute, old, new, kwargs ):
        if new != self.light_state_we_set:
            # triggered by button wired directly to relay (relay is retarded and does not report button state, only its own state)
            self.light_state_we_set = None
            self.debug( "on_light %s (%s -> %s)", entity, old, new )
            if new == "on":
                # light turned on by button: prolong timeout by button_delay
                self.timer.at_least( self.button_delay )
            else:
                # light turned off by button
                self.timer.reset()

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )


class MotionLightButton(hassapi.Hass):
    def initialize(self):
        self.depends_on_module( grug_timeout )
        self.__actor = MotionLightButtonActor( self, **self.args )

    def cancel(self):
        self.__actor.cancel()


