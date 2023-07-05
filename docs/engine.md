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

* :small_blue_diamond: **`GameScene`**`(self)` - 

#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`handle_message`**`(self, msg)` - 

  * **:arrow_forward: `msg:`** 
* :small_blue_diamond: **`paint`**`(self, surface)` - called once for every frame to paint the game state to the given surface

  * **:arrow_forward: `surface:`** 

  

* :small_blue_diamond: **`paintOverlay`**`(self, window, scale)` - called once for every frame for painting after the game surface has been resized to the display size.

  * **:arrow_forward: `window:`** the surface to paint

  * **:arrow_forward: `scale:`** the scale factor relative the the surface passed in to paint()

  This can be used for drawing smooth fonts by drawing the fonts to the game surface after resizing the surface for full screen mode.

  

* :small_blue_diamond: **`resizeEvent`**`(self, surface, scale)` - called when the window is resized

  * **:arrow_forward: `surface:`** 

  * **:arrow_forward: `scale:`** 

  new_size = (screen.get_width(), screen.get_height())

  

* :small_blue_diamond: **`update`**`(self, delta_t)` - called once for every frame to update the game state

  * **:arrow_forward: `delta_t:`** the amount of time that has elapsed since the last call. This value is stable and will be 1/FPS.

  

---
## Engine



#### Constructor:

* :small_blue_diamond: **`Engine`**`(self)` - 

#### Methods:

* :small_blue_diamond: **`afterFrame`**`(self)` - 
* :small_blue_diamond: **`beforeFrame`**`(self)` - 
* :small_blue_diamond: **`handle_event`**`(self, event)` - 

  * **:arrow_forward: `event:`** 
* :small_blue_diamond: **`init`**`(self, scene=None)` - 

  * **:arrow_forward: `scene:`** 
* :small_blue_diamond: **`run`**`(self)` - 
* :small_blue_diamond: **`screenpos`**`(self, windowpos)` - 

  * **:arrow_forward: `windowpos:`** 
* :small_blue_diamond: **`setActive`**`(self, active)` - 

  * **:arrow_forward: `active:`** 
* :small_blue_diamond: **`setScene`**`(self, scene)` - 

  * **:arrow_forward: `scene:`** 
* :small_blue_diamond: **`setWindowMode`**`(self)` - the first time this is called the environment variables are used to suggest  how to display the window

  subsequent calls require changing the window to a bogus value before updating the sdl_window and changing the mode to the new correct value

  


    ## Network Synchronized Objects


---
## KeyboardInputDevice
TODO: add an option to repeat sending direction or button press events




#### Constructor:

* :small_blue_diamond: **`KeyboardInputDevice`**`(self, direction_config, button_config, callback=None)` - 

  * **:arrow_forward: `direction_config:`** 

  * **:arrow_forward: `button_config:`** 

  * **:arrow_forward: `callback:`** 

#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`setCallback`**`(self, callback)` - 

  * **:arrow_forward: `callback:`** 
---
## JoystickInputDevice



#### Constructor:

* :small_blue_diamond: **`JoystickInputDevice`**`(self, instance_id, joy_config, button_config, callback=None)` - 

  * **:arrow_forward: `instance_id:`** 

  * **:arrow_forward: `joy_config:`** 

  * **:arrow_forward: `button_config:`** 

  * **:arrow_forward: `callback:`** 

#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`setCallback`**`(self, callback)` - 

  * **:arrow_forward: `callback:`** 
---
## NetworkPlayerState


---
## InputController
The update interval controls how often a [NetworkPlayerState](#large_blue_diamond-networkplayerstate) event is sent to the server. The server should send this event back to all other clients, so that it can be processed by the [RemoteInputController](#large_blue_diamond-remoteinputcontroller)

TODO: add an option to send input events to the server




#### Constructor:

* :small_blue_diamond: **`InputController`**`(self, input_device, entity, client=None, input_delay=5, update_interval=0.1)` - 

  * **:arrow_forward: `input_device:`** A keyboard or joystick input device

  * **:arrow_forward: `entity:`** The entity to pass input events to

  * **:arrow_forward: `client:`** the UdP client to use for sending information to the server

  * **:arrow_forward: `input_delay:`** The number of frames to delay user input before applying to the entity

  * **:arrow_forward: `update_interval:`** send the entity state to the serveral at this interval, default 100ms

  


#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`onUpdateTimeout`**`(self)` - 
* :small_blue_diamond: **`onUserInput`**`(self, event)` - 

  * **:arrow_forward: `event:`** 
* :small_blue_diamond: **`sendState`**`(self)` - 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## RemoteInputController



#### Constructor:

* :small_blue_diamond: **`RemoteInputController`**`(self, entity, input_delay=0.1)` - 

  * **:arrow_forward: `entity:`** 

  * **:arrow_forward: `input_delay:`** 

  


#### Methods:

* :small_blue_diamond: **`receiveState`**`(self, msg)` - 

  * **:arrow_forward: `msg:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 

    ## User Input


---
## Entity



#### Constructor:

* :small_blue_diamond: **`Entity`**`(self, rect=None)` - 

  * **:arrow_forward: `rect:`** 

#### Methods:

* :small_blue_diamond: **`getState`**`(self)` - get the current state of this entity

  reimplement this method to support network synchronization.

  At a minimum the state must have a 'clock' member variable. The clock must be monotonic (strictly increasing) count of frames.

  

* :small_blue_diamond: **`interpolateState`**`(self, state1, state2, p)` - blend two states together

  * **:arrow_forward: `state1:`** the initial state, acting as the starting point

  * **:arrow_forward: `state2:`** the target state

  * **:arrow_forward: `p:`** value between zero and one representing the amount of blending.

  reimplement this method to support network synchronization.

  a value of p=0 means to return state1, while a value of p=1 means to returns state2.  values between 0 and 1 should blend the states together.

  Note: the clock value, if set, will be ignored.

  

* :small_blue_diamond: **`onCollide`**`(self, ent, normal=None)` - called by the physics component on a collision with an entity

  * **:arrow_forward: `ent:`** 

  * **:arrow_forward: `normal:`** 

  

* :small_blue_diamond: **`paint`**`(self, surface)` - 

  * **:arrow_forward: `surface:`** 
* :small_blue_diamond: **`setState`**`(self, state)` - set the current state of this entity

  * **:arrow_forward: `state:`** 

  reimplement this method to support network synchronization.

  

* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## Physics2dComponent



#### Constructor:

* :small_blue_diamond: **`Physics2dComponent`**`(self, entity, map_rect=None, collision_group=None)` - 

  * **:arrow_forward: `entity:`** 

  * **:arrow_forward: `map_rect:`** 

  * **:arrow_forward: `collision_group:`** 

#### Methods:

* :small_blue_diamond: **`addImpulse`**`(self, dx, dy)` - 

  * **:arrow_forward: `dx:`** 

  * **:arrow_forward: `dy:`** 
* :small_blue_diamond: **`getState`**`(self)` - 
* :small_blue_diamond: **`interpolateState`**`(self, state1, state2, p)` - 

  * **:arrow_forward: `state1:`** 

  * **:arrow_forward: `state2:`** 

  * **:arrow_forward: `p:`** 
* :small_blue_diamond: **`paint`**`(self, surface)` - 

  * **:arrow_forward: `surface:`** 
* :small_blue_diamond: **`reset`**`(self)` - 
* :small_blue_diamond: **`setDirection`**`(self, vector)` - 

  * **:arrow_forward: `vector:`** 
* :small_blue_diamond: **`setState`**`(self, state)` - 

  * **:arrow_forward: `state:`** 
* :small_blue_diamond: **`speed`**`(self)` - 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## PlatformPhysics2dComponent



#### Constructor:

* :small_blue_diamond: **`PlatformPhysics2dComponent`**`(self, entity, map_rect=None, collision_group=None)` - 

  * **:arrow_forward: `entity:`** 

  * **:arrow_forward: `map_rect:`** 

  * **:arrow_forward: `collision_group:`** 

#### Methods:

* :small_blue_diamond: **`setDirection`**`(self, vector)` - 

  * **:arrow_forward: `vector:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## AdventurePhysics2dComponent



#### Constructor:

* :small_blue_diamond: **`AdventurePhysics2dComponent`**`(self, entity, map_rect=None, collision_group=None)` - 

  * **:arrow_forward: `entity:`** 

  * **:arrow_forward: `map_rect:`** 

  * **:arrow_forward: `collision_group:`** 

#### Methods:

* :small_blue_diamond: **`setDirection`**`(self, vector)` - 

  * **:arrow_forward: `vector:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## AnimationComponent



#### Constructor:

* :small_blue_diamond: **`AnimationComponent`**`(self, entity)` - 

  * **:arrow_forward: `entity:`** 

#### Methods:

* :small_blue_diamond: **`clear`**`(self)` - 
* :small_blue_diamond: **`getState`**`(self)` - 
* :small_blue_diamond: **`interpolateState`**`(self, state1, state2, p)` - 

  * **:arrow_forward: `state1:`** 

  * **:arrow_forward: `state2:`** 

  * **:arrow_forward: `p:`** 
* :small_blue_diamond: **`paint`**`(self, surface)` - paint the current animation

  * **:arrow_forward: `surface:`** 

  if the entities visible flag is false, nothing will be drawn

  if a transform is set, the transform function can change the image that will be drawn

  the image is drawn at the entities top left corver with an optional offset

  

* :small_blue_diamond: **`register`**`(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None)` - 

  * **:arrow_forward: `images:`** 

  * **:arrow_forward: `animated:`** 

  * **:arrow_forward: `offset:`** 

  * **:arrow_forward: `fps:`** 

  * **:arrow_forward: `loop:`** 

  * **:arrow_forward: `onend:`** 

  * **:arrow_forward: `onframe:`** 

  * **:arrow_forward: `interuptable:`** 

  * **:arrow_forward: `transform:`** 
* :small_blue_diamond: **`setAnimation`**`(self, images=None, animated=None, offset=None, fps=4, loop=True, onend=None, onframe=None, interuptable=True, transform=None)` - 

  * **:arrow_forward: `images:`** 

  * **:arrow_forward: `animated:`** 

  * **:arrow_forward: `offset:`** 

  * **:arrow_forward: `fps:`** 

  * **:arrow_forward: `loop:`** 

  * **:arrow_forward: `onend:`** 

  * **:arrow_forward: `onframe:`** 

  * **:arrow_forward: `interuptable:`** 

  * **:arrow_forward: `transform:`** 
* :small_blue_diamond: **`setAnimationById`**`(self, aid, **kwargs)` - 

  * **:arrow_forward: `aid:`** 

  * **:arrow_forward: `kwargs:`** 
* :small_blue_diamond: **`setState`**`(self, state)` - 

  * **:arrow_forward: `state:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
