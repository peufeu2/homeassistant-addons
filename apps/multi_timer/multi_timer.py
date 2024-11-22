import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib
import grug_timeout #, grug_gmqtt
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

class MultiTimerActor:
    def __init__( self, api ):
        self.api  = api
        self.args = api.args
        self.name = self.args["name"]
        self.topics = api.args["topics"]
        self.output = api.args["output"]
        self.output_state_we_set = None
        self.api.log("TOPICS: %s", self.topics)
        self.api.listen_state( self.on_output_changed, self.output )

        self.api.set_namespace( "userapps" )

        self.timer = grug_timeout.DelayedCallback( api, self.timer_callback, self.name+".timer" )

        # self.timer = grug_timeout.DelayedCallback( api, self.light_off, self.name+".timer" )    # normal timer to turn off the light
        # self.timeout = grug_timeout.DelayedCallback( api, self.light_off, self.name+".timeout" )  # stuck motion detector timeout
        # self.timer.load()
        # self.timeout.load()
        # self.light_state_we_set = None      # remember if it was us who set the light
        
        # self.sensor_state = {}
        # self.sensors = sensors
        # for sensor in sensors:
        #     api.listen_state( self.on_sensor, sensor )  # motion detector
        # api.listen_state( self.on_light, light )    # relay state change from wired button

        # # if light is on at app start, remember to turn it off
        # if self.api.get_state( self.light ) == "on":
        #     self.timer.set( self.args["button_delay"] )

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )

    def terminate(self):
        self.api.log('#### terminate')
        self.timer.cancel()

    def initialize( self ):
        self.mqtt = self.api.get_plugin_api("MQTT")
        for topic in self.topics:
            self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE", topic=topic )
        if not self.mqtt.is_client_connected():
            self.api.log('### MQTT is not connected')

    def mqtt_message_received_event( self, eventname, data, kwargs ):
        # self.api.log( "%s", { "eventname":eventname, "data":data, "kwargs":kwargs } )
        topic = data["topic"]
        payload = data["payload"]
        if not (d := self.topics.get( topic )):
            return self.debug( "Topic %r is not configured.", topic )
        if not (a := d.get( payload )):
            return self.debug( "Topic %r Payload %r is not configured.", topic, payload )
        if state := a.get("state"):
            self.timer.reset()
            if state == "off":
                self.output_state_we_set = "off"
                self.api.turn_off( self.output )
            elif state == "on":
                self.output_state_we_set = "on"
                self.api.turn_on( self.output )
        elif on_time := a.get( "on_time" ):
            self.output_state_we_set = "on"
            self.api.turn_on( self.output )
            self.timer.set( on_time )

    def timer_callback( self ):
        self.api.turn_off( self.output )

    def on_output_changed( self, entity, attribute, old, new, kwargs ):
        if new == self.output_state_we_set:
            # We caused this state change, ignore it.
            return
        
        # Manual control: cancel timer
        self.output_state_we_set = None
        self.debug( "on_output_changed %s (%s -> %s)", entity, old, new )
        self.timer.reset()

#   Using separate class here, to avoid conflicts between hassapi.Hass
#   member functions and variable and our own class stuff.
#
class MultiTimer(hassapi.Hass):
    def initialize(self):
        self.depends_on_module( grug_timeout )
        self.__actor = MultiTimerActor( self )
        self.__actor.initialize()

    def terminate(self):
        self.__actor.terminate()


