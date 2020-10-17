[Home](../README.md)


# Utility Classes

* [Timer](#timer)
* [LineGraph](#linegraph)
* [AreaGraph](#areagraph)
---
## :large_blue_diamond: Timer



#### Constructor:

* :small_blue_diamond: **`Timer`**`(self, duration=0, callback=None)` - 

  * **:arrow_forward: `duration:`** 

  * **:arrow_forward: `callback:`** 

#### Methods:

* :small_blue_diamond: **`setInterval`**`(self, duration, callback)` - 

  * **:arrow_forward: `duration:`** 

  * **:arrow_forward: `callback:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## :large_blue_diamond: LineGraph



#### Constructor:

* :small_blue_diamond: **`LineGraph`**`(self, rect, samples, title, callback, text_transform)` - 

  * **:arrow_forward: `rect:`** 

  * **:arrow_forward: `samples:`** 

  * **:arrow_forward: `title:`** 

  * **:arrow_forward: `callback:`** 

  * **:arrow_forward: `text_transform:`** 

#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`handle_message`**`(self, msg)` - 

  * **:arrow_forward: `msg:`** 
* :small_blue_diamond: **`paint`**`(self, surface)` - 

  * **:arrow_forward: `surface:`** 
* :small_blue_diamond: **`setLineTitle`**`(self, titles)` - 

  * **:arrow_forward: `titles:`** 
* :small_blue_diamond: **`setRange`**`(self, vmin, vmax)` - 

  * **:arrow_forward: `vmin:`** 

  * **:arrow_forward: `vmax:`** 
* :small_blue_diamond: **`setShowLabels`**`(self, show)` - 

  * **:arrow_forward: `show:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
---
## :large_blue_diamond: AreaGraph



#### Constructor:

* :small_blue_diamond: **`AreaGraph`**`(self, rect, samples, callback)` - 

  * **:arrow_forward: `rect:`** 

  * **:arrow_forward: `samples:`** 

  * **:arrow_forward: `callback:`** 

#### Methods:

* :small_blue_diamond: **`handle_event`**`(self, evt)` - 

  * **:arrow_forward: `evt:`** 
* :small_blue_diamond: **`handle_message`**`(self, msg)` - 

  * **:arrow_forward: `msg:`** 
* :small_blue_diamond: **`paint`**`(self, surface)` - 

  * **:arrow_forward: `surface:`** 
* :small_blue_diamond: **`update`**`(self, delta_t)` - 

  * **:arrow_forward: `delta_t:`** 
