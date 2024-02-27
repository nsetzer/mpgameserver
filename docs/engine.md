[Home](../README.md)
* [GameScene](#gamescene)
* [Engine](#engine)
* [KeyboardInputDevice](#keyboardinputdevice)
* [JoystickInputDevice](#joystickinputdevice)
* [NetworkPlayerState](#networkplayerstate)
* [InputController](#inputcontroller)
* [RemoteInputController](#remoteinputcontroller)
* [Entity](#entity)
* [Physics2dComponent](#physics2dcomponent)
* [PlatformPhysics2dComponent](#platformphysics2dcomponent)
* [AdventurePhysics2dComponent](#adventurephysics2dcomponent)
* [AnimationComponent](#animationcomponent)

# Pygame Engine


    ## Pygame Engine
---
## GameScene



#### Constructor:

 **GameScene**`(self)` - 

#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **handle_message**`(self, msg)` - 

  * **msg:** 
 **paint**`(self, surface)` - called once for every frame to paint the game state to the given surface

  * **surface:** 

  

 **paintOverlay**`(self, window, scale)` - called once for every frame for painting after the game surface has been resized to the display size.

  * **window:** the surface to paint

  * **scale:** the scale factor relative the the surface passed in to paint()

  This can be used for drawing smooth fonts by drawing the fonts to the game surface after resizing the surface for full screen mode.

  

 **resizeEvent**`(self, surface, scale)` - called when the window is resized

  * **surface:** 

  * **scale:** 

  new_size = (screen.get_width(), screen.get_height())

  

 **update**`(self, delta_t)` - called once for every frame to update the game state

  * **delta_t:** the amount of time that has elapsed since the last call. This value is stable and will be 1/FPS.

  

---
## Engine



#### Constructor:

 **Engine**`(self)` - 

#### Methods:

 **afterFrame**`(self)` - 
 **beforeFrame**`(self)` - 
 **handle_event**`(self, event)` - 

  * **event:** 
 **init**`(self, scene=None)` - 

  * **scene:** 
 **run**`(self)` - 
 **screenpos**`(self, windowpos)` - 

  * **windowpos:** 
 **setActive**`(self, active)` - 

  * **active:** 
 **setScene**`(self, scene)` - 

  * **scene:** 
 **setWindowMode**`(self)` - the first time this is called the environment variables are used to suggest  how to display the window

  subsequent calls require changing the window to a bogus value before updating the sdl_window and changing the mode to the new correct value

  


    ## Network Synchronized Objects


---
## KeyboardInputDevice
TODO: add an option to repeat sending direction or button press events




#### Constructor:

 **KeyboardInputDevice**`(self, direction_config, button_config, callback=None)` - 

  * **direction_config:** 

  * **button_config:** 

  * **callback:** 

#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **setCallback**`(self, callback)` - 

  * **callback:** 
---
## JoystickInputDevice



#### Constructor:

 **JoystickInputDevice**`(self, instance_id, joy_config, button_config, callback=None)` - 

  * **instance_id:** 

  * **joy_config:** 

  * **button_config:** 

  * **callback:** 

#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **setCallback**`(self, callback)` - 

  * **callback:** 
---
## NetworkPlayerState


---
## InputController
The update interval controls how often a [NetworkPlayerState](#large_blue_diamond-networkplayerstate) event is sent to the server. The server should send this event back to all other clients, so that it can be processed by the [RemoteInputController](#large_blue_diamond-remoteinputcontroller)

TODO: add an option to send input events to the server




#### Constructor:

 **InputController**`(self, input_device, entity, client=None, input_delay=5, update_interval=0.1)` - 

  * **input_device:** A keyboard or joystick input device

  * **entity:** The entity to pass input events to

  * **client:** the UdP client to use for sending information to the server

  * **input_delay:** The number of frames to delay user input before applying to the entity

  * **update_interval:** send the entity state to the serveral at this interval, default 100ms

  


#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **onUpdateTimeout**`(self)` - 
 **onUserInput**`(self, event)` - 

  * **event:** 
 **sendState**`(self)` - 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## RemoteInputController



#### Constructor:

 **RemoteInputController**`(self, entity, input_delay=0.1)` - 

  * **entity:** 

  * **input_delay:** 

  


#### Methods:

 **receiveState**`(self, msg)` - 

  * **msg:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 

    ## User Input


---
## Entity



#### Constructor:

 **Entity**`(self, rect=None)` - 

  * **rect:** 

#### Methods:

 **getState**`(self)` - get the current state of this entity

  reimplement this method to support network synchronization.

  At a minimum the state must have a 'clock' member variable. The clock must be monotonic (strictly increasing) count of frames.

  

 **interpolateState**`(self, state1, state2, p)` - blend two states together

  * **state1:** the initial state, acting as the starting point

  * **state2:** the target state

  * **p:** value between zero and one representing the amount of blending.

  reimplement this method to support network synchronization.

  a value of p=0 means to return state1, while a value of p=1 means to returns state2.  values between 0 and 1 should blend the states together.

  Note: the clock value, if set, will be ignored.

  

 **onCollide**`(self, ent, normal=None)` - called by the physics component on a collision with an entity

  * **ent:** 

  * **normal:** 

  

 **paint**`(self, surface)` - 

  * **surface:** 
 **setState**`(self, state)` - set the current state of this entity

  * **state:** 

  reimplement this method to support network synchronization.

  

 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## Physics2dComponent



#### Constructor:

 **Physics2dComponent**`(self, entity, map_rect=None, collision_group=None)` - 

  * **entity:** 

  * **map_rect:** 

  * **collision_group:** 

#### Methods:

 **addImpulse**`(self, dx, dy)` - 

  * **dx:** 

  * **dy:** 
 **getState**`(self)` - 
 **interpolateState**`(self, state1, state2, p)` - 

  * **state1:** 

  * **state2:** 

  * **p:** 
 **paint**`(self, surface)` - 

  * **surface:** 
 **reset**`(self)` - 
 **setDirection**`(self, vector)` - 

  * **vector:** 
 **setState**`(self, state)` - 

  * **state:** 
 **speed**`(self)` - 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## PlatformPhysics2dComponent



#### Constructor:

 **PlatformPhysics2dComponent**`(self, entity, map_rect=None, collision_group=None)` - 

  * **entity:** 

  * **map_rect:** 

  * **collision_group:** 

#### Methods:

 **setDirection**`(self, vector)` - 

  * **vector:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## AdventurePhysics2dComponent



#### Constructor:

 **AdventurePhysics2dComponent**`(self, entity, map_rect=None, collision_group=None)` - 

  * **entity:** 

  * **map_rect:** 

  * **collision_group:** 

#### Methods:

 **setDirection**`(self, vector)` - 

  * **vector:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## AnimationComponent



#### Constructor:

 **AnimationComponent**`(self, entity)` - 

  * **entity:** 

#### Methods:

 **clear**`(self)` - 
 **getState**`(self)` - 
 **interpolateState**`(self, state1, state2, p)` - 

  * **state1:** 

  * **state2:** 

  * **p:** 
 **paint**`(self, surface)` - paint the current animation

  * **surface:** 

  if the entities visible flag is false, nothing will be drawn

  if a transform is set, the transform function can change the image that will be drawn

  the image is drawn at the entities top left corver with an optional offset

  

 **register**`(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None)` - 

  * **images:** 

  * **animated:** 

  * **offset:** 

  * **fps:** 

  * **loop:** 

  * **onend:** 

  * **onframe:** 

  * **interuptable:** 

  * **transform:** 
 **setAnimation**`(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None)` - 

  * **images:** 

  * **animated:** 

  * **offset:** 

  * **fps:** 

  * **loop:** 

  * **onend:** 

  * **onframe:** 

  * **interuptable:** 

  * **transform:** 
 **setAnimationById**`(self, aid, **kwargs)` - 

  * **aid:** 

  * **kwargs:** 
 **setState**`(self, state)` - 

  * **state:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
