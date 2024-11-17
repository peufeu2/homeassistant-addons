# Motion activated light with button

## Problem

I have a stairwell with bends. An old mechanical light timer was already installed, controlled by several momentary pushbuttons. This has all the usual drawbacks: there are not enough buttons, and you have to reset the timer every 2 minutes when vacuuming the area.

## Solution

The mechanical timer is replaced with a Sonoff ZBMiniR2. It controls the lights and takes the existing pushbuttons as input.

Zigbee motion sensors are placed in the stairwell.

Basic behavior is the same as any motion activated light:
- When occupancy is detected, lights turns on.
- As long as any sensor detects occupancy, lights remains on.
- When no sensor detects occupancy, a timer starts, waits for motion_timer seconds, and turns off the lights. If any sensor detects occupancy again, the timer is canceled and lights stay on.

Extra features: 

The buttons are still connected to the Zigbee relay, so pressing them will toggle the light. This keeps it functional even if home automation is down.

If the light is on and the button is pressed, lights turns off. It will turn back on when any sensor transitions from "no occupancy" to "occupancy". So it is possible to turn off the lights while standing in front of a sensor, then leave the room without lights turning back on immediately.

If the light is off and the button is pressed, lights will turn on and remain on for button_delay, typically much longer than motion_delay. During this time, motion sensors will not turn off the light, but they can keep it on for longer after the button timer exires.

In other words, single click means turn off, and double clicking the button means forcing the lights on for an hour.

The subtlety is that the relay does not report its input state, only changes in its output state, so this program has to distinguish between a change in relay state from the button being pressed, and a change from a zigbee command.




