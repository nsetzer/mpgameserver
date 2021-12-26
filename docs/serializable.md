[Home](../README.md)


# Message Serialization

To send messages between the client and server the message must first be encoded to a byte array.
MpGameServer does not do this automatically so a third party library will be needed

> :warning: It is highly recommended to use a well tested library such as [protobuf](https://pypi.org/project/protobuf) or [msgpack](https://pypi.org/project/msgpack)
> These libraries are cross-platform, and cross-language and will make migrating away from MpGameServer easier, although can be more complicated to get set up.

> :x: Do not use python pickle for serialization. It is *never* a good idea to unpickle an untrusted message, as this could lead to remote code execution.

If you are willing to ignore the warning, then MpGameServer includes a pure-python serialization library.
This libraries primary goal is to combine ease of use while allowing for customization of the byte encoding for performance sensitive messages.
The secondary goal is to allow for human readable configuration using strongly typed JSON.
To support typed JSON the library makes heavy use of Python's type hinting.

There are two basic types provided. A `Serializable` contains a collection of data, and `Serializable` types can be nested.
A `SerializableEnum` is used to define an enumeration that can be serialized.

As a simple example, one way to encode a player's position in a 2D side scrolling game is to define the direction the player
is facing as well as the current position.

```python

from typing import List, Dict, Tuple

class Direction(SerializableEnum):
    LEFT=1
    RIGHT=2

class PlayerPosition(Serializable):
    position: Tuple[int, int] = (0, 0)
    facing: Direction = Direction.LEFT

player_pos = PlayerPosition(position=(16,32))

print(player_pos) # print a debug representation
"PlayerPosition({'position':(16, 32), 'facing':Direction.LEFT})"

print(player_pos.dumpb()) # print the byte representation
b'\x00\x81\x00\x10\x00\x03\x02\x00\x03\x10\x00\x03\x10\x00\x80\x00\x03\x01' # 18 bytes

print(player_pos.dumps()) # print a JSON string representation
'{"position": [16, 32], "facing": "LEFT"}' # 40 bytes

# encode/decode the message from bytes
encoded_message = player_pos.dumpb()
print(Serializable.loadb(encoded_message))
PlayerPosition({'position':(16, 32), 'facing':Direction.LEFT})

# encode/decode the message from a string
encoded_message = player_pos.dumps()
print(PlayerPosition.loads(encoded_message))
{"position": [16, 32], "facing": "LEFT"}

```

> :warning: Serializable types are automatically assigned a unique integer Id when the class is defined.
> This Id is used to serialize and deserialize a byte array and thus needs to be the same between the client and server.
> Ensure the client and server define the same types in the same order, and the import order for any modules is the same.


* [SerializableType](#serializabletype)
* [Serializable](#serializable)
* [SerializableEnum](#serializableenum)
---
## :large_blue_diamond: SerializableType
Classes that derive from Serializable or SerializableEnum are automatically assigned a unique id which is used to serialize/deserialize to/from a byte representation.

This class exposes a method to control what the next unique id will be before a class definition. You shouldn't need to use this under normal operation.




#### Static Methods:

* :small_blue_diamond: **`setRootId`**`(module, base_type_id)` - Change the next uid for SerializableTypes defined in a given module

  * **:arrow_forward: `module:`** the name of a module

  * **:arrow_forward: `base_type_id:`** the first type id to assign for a given module

  After calling this method all classes that are defined in the current file will be enumerated in order starting with the given type_id

  this can be called multiple times within a given file to change the next id

  usage:

  

          ```
            SerializableType.setRootId(__name__, 2048)
        ```

  

---
## :large_blue_diamond: Serializable
Base class for defining a new serializable class. Sub Classes of Serializable can be converted to and from byte representations as well as JSON string representations.




#### Constructor:

* :small_blue_diamond: **`Serializable`**`(self, **kwargs)` - 

  * **:arrow_forward: `kwargs:`** 

#### Public Attributes:

**`type_id`**: Automatically assigned unique type identifier for this class/instance. type_id is a special attribute which can be set in the class definition to override the type_id used for the class. Values less than 256 are reserverd for use by MpGameServer.


#### Class Methods:

* :small_blue_diamond: **`fromJson`**`(record)` - initialize a new instance of Type from a JSON object

  * **:arrow_forward: `record:`** a JSON object

  Uses the type annotations for members of Type to determine how to convert the JSON object attributes into member attributes

  This will recursivley convert child attributes made up of iterable and mapping types.

  Invalid keys in the given record are ignored.

  

* :small_blue_diamond: **`loads`**`(string, **kwargs)` - 

  * **:arrow_forward: `string:`** 

  * **:arrow_forward: `kwargs:`** 

#### Static Methods:

* :small_blue_diamond: **`loadb`**`(stream, **kwargs)` - 

  * **:arrow_forward: `stream:`** 

  * **:arrow_forward: `kwargs:`** 

#### Methods:

* :small_blue_diamond: **`deserialize`**`(self, stream, **kwargs)` - populate member attributes by reading fields from a stream.

  * **:arrow_forward: `stream:`** a file like object opened for reading bytes from.

  * **:arrow_forward: `kwargs:`** extra arguments that are passed to deserialize, a specialization of deserialize can use kwargs to control how the class is deserialized

  * **:leftwards_arrow_with_hook: `returns:`** self

  Note: the return value can be any serializable type to implement versioning, old versions can be deserialized and then convert to the new version and return that instead by reimplementing this function for that type.

  

* :small_blue_diamond: **`dumpb`**`(self, **kwargs)` - return a byte array representation of this class

  * **:arrow_forward: `kwargs:`** extra arguments that are passed to deserialize, a specialization of deserialize can use kwargs to control how the class is deserialized

  

* :small_blue_diamond: **`dumps`**`(self, indent=None, sort_keys=False, **kwargs)` - 

  * **:arrow_forward: `indent:`** 

  * **:arrow_forward: `sort_keys:`** 

  * **:arrow_forward: `kwargs:`** 
* :small_blue_diamond: **`serialize`**`(self, stream, **kwargs)` - Write the content of this class to the stream

  * **:arrow_forward: `stream:`** a file like object opened for writing bytes to.

  * **:arrow_forward: `kwargs:`** 

  

* :small_blue_diamond: **`serialize_header`**`(self, stream)` - Writes a header to the stream

  * **:arrow_forward: `stream:`** a file like object opened for writing bytes to.

  

* :small_blue_diamond: **`toJson`**`(self)` - return a JSON object representation of this class

  JSON uses a limited subset of valid python types. In particular, the following transforms are performed:

  1. dictionary keys are converted to strings. the key type must accept converting a string representation back to the native typein order for a round trip through Serializable.fromJson to work correctly. SerializableEnum can be used as a key in a dictionary, as can integers. 2. SerializableEnum are converted to a string representation 3. List/Set/Tuple are all converted to a list. With proper type annotation hints, these types can all be correctly round-tripped with Serializable.fromJson.

  In addition, no conversion is done for float types. This means that invalid JSON float values are not modified.

  

---
## :large_blue_diamond: SerializableEnum
SerializableEnum is a reimplementation of Python's Enum with support for use in a Serializable.

A SerializableEnum can be used as part of a Generic specifier, for either typing.List or typing.Tuple as well as either a key or value in typing.Dict




#### Constructor:

* :small_blue_diamond: **`SerializableEnum`**`(self, value=None)` - 

  * **:arrow_forward: `value:`** 

#### Public Attributes:

**`value`**: get the underlying value of the enum


#### Class Methods:

* :small_blue_diamond: **`fromJson`**`(value)` - 

  * **:arrow_forward: `value:`** 

#### Methods:

* :small_blue_diamond: **`deserialize`**`(self, stream, **kwargs)` - 

  * **:arrow_forward: `stream:`** a file like object opened for writing bytes to.

  * **:arrow_forward: `kwargs:`** 

  

* :small_blue_diamond: **`name`**`(self)` - return a string representation of the enum value
* :small_blue_diamond: **`serialize`**`(self, stream, **kwargs)` - write the current value to a stream

  * **:arrow_forward: `stream:`** a file like object opened for writing bytes to.

  * **:arrow_forward: `kwargs:`** 

  

* :small_blue_diamond: **`serialize_header`**`(self, stream)` - 

  * **:arrow_forward: `stream:`** a file like object opened for writing bytes to.

  

* :small_blue_diamond: **`toJson`**`(self)` - return a dictionary suitable for passing to json.dumps

  

