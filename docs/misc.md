[Home](../README.md)


# Utility Classes

* [Timer](#timer)
* [LineGraph](#linegraph)
* [AreaGraph](#areagraph)
---
## Timer



#### Constructor:

 **Timer**`(self, duration=0, callback=None)` - 

  * **duration:** 

  * **callback:** 

#### Methods:

 **reset**`(self)` - 
 **setInterval**`(self, duration, callback)` - 

  * **duration:** 

  * **callback:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## LineGraph



#### Constructor:

 **LineGraph**`(self, rect, samples, title, callback, text_transform, font_size=16)` - 

  * **rect:** 

  * **samples:** 

  * **title:** 

  * **callback:** 

  * **text_transform:** 

  * **font_size:** 

#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **handle_message**`(self, msg)` - 

  * **msg:** 
 **paint**`(self, surface)` - 

  * **surface:** 
 **setLineTitle**`(self, titles)` - 

  * **titles:** 
 **setRange**`(self, vmin, vmax)` - 

  * **vmin:** 

  * **vmax:** 
 **setShowLabels**`(self, show)` - 

  * **show:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
---
## AreaGraph



#### Constructor:

 **AreaGraph**`(self, rect, samples, callback)` - 

  * **rect:** 

  * **samples:** 

  * **callback:** 

#### Methods:

 **handle_event**`(self, evt)` - 

  * **evt:** 
 **handle_message**`(self, msg)` - 

  * **msg:** 
 **paint**`(self, surface)` - 

  * **surface:** 
 **update**`(self, delta_t)` - 

  * **delta_t:** 
