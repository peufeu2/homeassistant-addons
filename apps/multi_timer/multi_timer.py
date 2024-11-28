import appdaemon.plugins.hass.hassapi as hassapi
import time, importlib
import grug_timeout #, grug_gmqtt
# importlib.reload( shared.timeout )

"""
    Multi-button scene controller -> one timer per button -> switch
"""
class MultiTimerActor:
    def __init__( self, api ):
        self.api  = api
        self.args = api.args
        self.name = self.args["name"]
        self.trigger_topics = api.args["trigger_topics"]
        self.output_switch  = api.args["output_switch"]
        self.output_state_we_set = None
        self.debug("Output: %s Triggers: %s", self.output_switch, self.trigger_topics)

        self.api.listen_state( self.on_output_changed, self.output_switch )
        self.timer = grug_timeout.DelayedCallback( api, self.timer_callback, self.name+".timer" )
        self.timer.load()
        self.api.log("Timer remaining: %s s", self.timer.remaining())

    def debug( self, fmt, *args ):
        self.api.log( fmt, *args, level="DEBUG" )

    def terminate(self):
        self.api.log('#### terminate')
        self.timer.cancel()

    def initialize( self ):
        self.mqtt = self.api.get_plugin_api("MQTT")
        for topic in self.trigger_topics:
            self.mqtt.listen_event(self.mqtt_message_received_event, "MQTT_MESSAGE", topic=topic )
        if not self.mqtt.is_client_connected():
            self.api.log('### MQTT is not connected')

    def mqtt_message_received_event( self, eventname, data, kwargs ):
        # self.api.log( "%s", { "eventname":eventname, "data":data, "kwargs":kwargs } )
        topic = data["topic"]
        payload = data["payload"]
        if not (trigger_actions := self.trigger_topics.get( topic )):
            return self.debug( "Topic %r is not configured.", topic )
        if not (action := trigger_actions.get( payload )):
            return self.debug( "Topic %r Payload %r is not configured.", topic, payload )
        if state := action.get("state"):
            self.timer.reset()
            if state == "off":
                self.output_state_we_set = "off"
                self.api.turn_off( self.output_switch )
            elif state == "on":
                self.output_state_we_set = "on"
                self.api.turn_on( self.output_switch )
        elif on_time := action.get( "on_time" ):
            self.output_state_we_set = "on"
            self.api.turn_on( self.output_switch )
            self.timer.set( on_time )

    def timer_callback( self ):
        self.api.turn_off( self.output_switch )

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


