import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib
import grug_timeout
# importlib.reload( shared.timeout )

"""
    Motion activated light with extra button.

    sensors:        A list of motion sensors, as HA entities.
    light:          Light entity to control.
    motion_delay:   Time to keep the light on after motion is no longer detected
    button_delay:   Time to keep the light on after the button is pressed
    timeout:        To turn off the light if the motion sensor stays stuck in ON state 

    set log_level DEBUG in this app's yaml config for logging.
"""

class MotionLightButtonActor:
    def __init__( self, api, name, sensors, light, **kwargs ):
        self.api    = api
        self.name   = name
        self.light  = light
        self.args   = kwargs
        self.api.set_namespace( "userapps" )

        self.timer = grug_timeout.DelayedCallback( api, self.light_off, self.name+".timer" )    # normal timer to turn off the light
        self.timeout = grug_timeout.DelayedCallback( api, self.light_off, self.name+".timeout" )  # stuck motion detector timeout
        self.timer.load()
        self.timeout.load()
        self.light_state_we_set = None      # remember if it was us who set the light
        
        self.sensor_state = {}
        self.sensors = sensors
        for sensor in sensors:
            api.listen_state( self.on_sensor, sensor )  # motion detector
        api.listen_state( self.on_light, light )    # relay state change from wired button

        # if light is on at app start, remember to turn it off
        if self.api.get_state( self.light ) == "on":
            self.timer.set( self.args["button_delay"] )

    def cancel(self):
        self.timer.cancel()
    
    "Turn the light off and remember we turned it off"
    def light_off( self ):
        self.debug( "light_off" )
        self.timeout.reset()
        self.light_state_we_set = "off"
        self.api.turn_off( self.light )

    "Turn the light on and remember we turned it on"
    def light_on( self ):
        self.debug( "light_on" )
        self.light_state_we_set = "on"
        self.api.turn_on( self.light )
    
    """Motion sensor state change
    
    If the light was turned off by the button, the sensor in front of the
    button reports occupancy, so it will not send new events until cleared.
    This allows leaving the room after turning the lights off with the button.
    
    But if someone comes from the other end of the corridor and activates another
    sensor, we want the lights to turn on. So we can't use a composite/group sensor,
    because that would already be on due to  the person pushing the button.

    Instead we have to check events from each sensor.
    """
    def on_sensor( self, entity, attribute, old, new, kwargs ):
        old_states = [ self.sensor_state.get(id) for id in self.sensors ]
        self.sensor_state[ entity ] = new
        new_states = [ self.sensor_state.get(id) for id in self.sensors ]
        self.debug( "on_sensor %s (%s -> %s) states %s -> %s", entity, old, new, old_states, new_states )
      
        #   Any sensor state change to "occupancy on" will turn on the lights
        if new == "on":               # presence detected
            self.timer.cancel()       # stop countdown, this does not clear the expiry time
            self.timeout.set( self.args["timeout"] )
            self.light_on()           # so the timer remembers if it was set by the button or sensor

        #   Turn off only when all sensors do not report "on" (ie, "off" or "unavailable")
        elif "on" not in new_states:
            # if self.api.get_state( self.light ) == "on":
            self.timeout.reset()      # cancel stuck motion detector timeout
            self.timer.at_least( self.args["motion_delay"] )    # Begin countdown. This will not shorten the timeout set by the button.

    """
    Relay state change, either from zigbee command or pushbutton wired to relay input.
    """
    def on_light( self, entity, attribute, old, new, kwargs ):
        if new == self.light_state_we_set:
            # We caused this state change, ignore it.
            return
        
        # Relay state change is from pushbutton wired to relay input.
        self.light_state_we_set = None
        self.debug( "on_light %s (%s -> %s)", entity, old, new )
        if new == "on":
            # light turned on by button: prolong timeout by button_delay
            self.timeout.reset()
            self.timer.at_least( self.args["button_delay"] )
        else:
            # light turned off by button. Cancel timer and reset expiry time.
            self.timeout.reset()
            self.timer.reset()

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )

#   Using separate class here, to avoid conflicts between hassapi.Hass
#   member functions and variable and our own class stuff.
#
class MotionLightButton(hassapi.Hass):
    def initialize(self):
        self.depends_on_module( grug_timeout )
        self.__actor = MotionLightButtonActor( self, **self.args )

    def cancel(self):
        self.__actor.cancel()


