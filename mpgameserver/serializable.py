#! python3 $this

"""
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
b'\\x00\\x81\\x00\\x10\\x00\\x03\\x02\\x00\\x03\\x10\\x00\\x03\\x10\\x00\\x80\\x00\\x03\\x01' # 18 bytes

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

"""
import json
import struct
from typing import NewType, Generic, List, Dict, Tuple, get_args, get_origin
from collections.abc import Iterable, Sequence, Mapping
import sys
import logging
from io import BytesIO
from enum import Enum
import gzip

# maximum string or bytes length is 1mb.
MAX_BYTES_LENGTH = 2**20

MAX_ARRAY_LENGTH = 2**14

class SerializableBaseTypes(object):

    bool_t    = 1

    intv_t    = 2  # placeholder for variable length encoding
    int8_t    = 3
    int16_t   = 4
    int32_t   = 5
    int64_t   = 6

    uintv_t   = 7  # placeholder for variable length encoding
    uint8_t   = 8
    uint16_t  = 9
    uint32_t  = 10
    uint64_t  = 11

    float32_t  = 11
    float64_t  = 12

    string_t  = 13
    bytes_t   = 14

    null_t    = 15

    seq_t    = 16
    map_t    = 17
    set_t    = 18

def ispublic(cls, name):
    return not name.startswith("_") and name != 'type_id' and not callable(getattr(cls, name))

class SerializableType(type):
    """
    Classes that derive from Serializable or SerializableEnum are automatically
    assigned a unique id which is used to serialize/deserialize to/from a byte representation.

    This class exposes a method to control what the next unique id will be before
    a class definition. You shouldn't need to use this under normal operation.

    """
    # numbers less than 128 are reserverd for builtin types
    next_type_id = 128
    custom_id = {}
    registry = {}
    names = {}

    def __new__(metacls, name, bases, namespace):
        cls = super().__new__(metacls, name, bases, namespace)
        # allow a user to specify exactly the type_id in the class def
        # or generate a new type_id when one is not defined.
        if name == 'Serializable':
            return cls
        parent_type = cls.mro()[1]
        if not hasattr(cls, '__annotations__'):
            cls.__annotations__ = {}
        if not hasattr(cls, 'type_id') or parent_type.type_id == cls.type_id:
            if cls.__module__ in SerializableType.custom_id:
                cls.type_id = SerializableType.custom_id[cls.__module__]
                SerializableType.custom_id[cls.__module__] += 1
            else:
                cls.type_id = SerializableType.next_type_id
                SerializableType.next_type_id += 1
        #print("%5d %s" % (cls.type_id, cls.__name__))
        if cls.type_id in SerializableType.registry:
            raise ValueError("Serializable ID %d:%s already in use" % (cls.type_id, cls))
        if cls.__name__ in SerializableType.names:
            raise ValueError("Serializable Name %d:%s already in use" % (cls.type_id, cls.__name__))
        SerializableType.registry[cls.type_id] = cls
        SerializableType.names[cls.__name__] = cls
        # TODO: use the __annotations__ to determine fields without default values
        cls._fields = tuple(name for name in cls.__dict__ if ispublic(cls, name))
        for field in cls._fields:
            if field not in cls.__annotations__:
                logging.info("missing annotation for %s.%s\n" % (cls.__name__, field))
        return cls

    @staticmethod
    def setRootId(module, base_type_id):
        """
        Change the next uid for SerializableTypes defined in a given module

        :param module: the name of a module
        :param base_type_id: the first type id to assign for a given module

        After calling this method all classes that are defined in the current
        file will be enumerated in order starting with the given type_id

        this can be called multiple times within a given file to change the
        next id

        usage:

        ```
            SerializableType.setRootId(__name__, 2048)
        ```
        """
        SerializableType.custom_id[module] = base_type_id

def serialize_bool(stream, value):
    stream.write(struct.pack(">H?", SerializableBaseTypes.bool_t, value))

def serialize_int(stream, value):

    #print(struct.unpack(">L", b"\x7F\xFF\xFF\xFF"))
    #print(struct.unpack(">l", b"\x7F\xFF\xFF\xFF"))
    a = abs(value)
    if a > 0x7FFFFFFF:
        stream.write(struct.pack(">Hq", SerializableBaseTypes.int64_t, value))
    elif a > 0x7FFF:
        stream.write(struct.pack(">Hl", SerializableBaseTypes.int32_t, value))
    elif a > 0x7F:
        stream.write(struct.pack(">Hh", SerializableBaseTypes.int16_t, value))
    else:
        stream.write(struct.pack(">Hb", SerializableBaseTypes.int8_t, value))

def serialize_float(stream, value):
    """
    floating point values are always serialized to a 4 byte float.
    """
    stream.write(struct.pack(">Hf", SerializableBaseTypes.float32_t, value))

def serialize_string(stream, value):

    enc = value.encode("utf-8")
    if len(enc) > MAX_BYTES_LENGTH:
        raise ValueError("string length too large: %d" % length)

    stream.write(struct.pack(">H", SerializableBaseTypes.string_t))
    serialize_int(stream, len(enc))
    stream.write(enc)

def serialize_bytes(stream, value):

    if len(value) > MAX_BYTES_LENGTH:
        raise ValueError("string length too large: %d" % len(value))

    stream.write(struct.pack(">H", SerializableBaseTypes.bytes_t))
    serialize_int(stream, len(value))
    stream.write(value)

def serialize_null(stream, value):
    stream.write(struct.pack(">H", SerializableBaseTypes.null_t))

serialize_types = {
    bool: serialize_bool,
    int: serialize_int,
    float: serialize_float,
    str: serialize_string,
    bytes: serialize_bytes,
    type(None): serialize_null,
}

def serialize_value(stream, value, **kwargs):

    t = type(value)

    if t in serialize_types:
        err = None
        try:
            serialize_types[t](stream, value)
        except struct.error as e:
            err = ValueError("unable to serialize %s %r: %s" % (t.__name__, value, e))
        if err:
            raise err

    elif isinstance(value, Serializable):
        #stream.write(struct.pack(">H", value.type_id))
        value.serialize_header(stream)
        value.serialize(stream, **kwargs)
    elif isinstance(value, SerializableEnum):
        #stream.write(struct.pack(">H", value.type_id))
        value.serialize_header(stream)
        value.serialize(stream, **kwargs)
    else:
        raise TypeError("%s" % type(value))

def serialize_map(stream, value):
    if len(value) > MAX_ARRAY_LENGTH:
        raise ValueError("map is too long")
    stream.write(struct.pack(">H", SerializableBaseTypes.map_t))
    serialize_value(stream, len(value))
    for k, v in value.items():
        serialize_value(stream, k)
        serialize_value(stream, v)

def serialize_seq(stream, value):
    if len(value) > MAX_ARRAY_LENGTH:
        raise ValueError("sequence is too long")
    stream.write(struct.pack(">H", SerializableBaseTypes.seq_t))
    serialize_value(stream, len(value))
    for v in value:
        serialize_value(stream, v)

def serialize_set(stream, value):
    if len(value) > MAX_ARRAY_LENGTH:
        raise ValueError("set is too long")
    stream.write(struct.pack(">H", SerializableBaseTypes.set_t))
    serialize_value(stream, len(value))
    for v in value:
        serialize_value(stream, v)

serialize_types[dict] = serialize_map
serialize_types[tuple] = serialize_seq
serialize_types[list] = serialize_seq
serialize_types[set] = serialize_set

def serialize_registry(stream, **kwargs):

    serialize_value(stream, len(SerializableType.registry), **kwargs)
    for type_id, cls in SerializableType.registry.items():
        serialize_value(stream, type_id, **kwargs)
        serialize_value(stream, cls.__name__, **kwargs)

# ----------------------------------

class SerializableError(Exception):
    pass

class SerializableHeaderError(SerializableError):
    pass

deserialize_bool_t    = lambda stream: struct.unpack(">?", stream.read(1))[0]
deserialize_int8_t    = lambda stream: struct.unpack(">b", stream.read(1))[0]
deserialize_int16_t   = lambda stream: struct.unpack(">h", stream.read(2))[0]
deserialize_int32_t   = lambda stream: struct.unpack(">l", stream.read(4))[0]
deserialize_int64_t   = lambda stream: struct.unpack(">q", stream.read(8))[0]
deserialize_uint8_t   = lambda stream: struct.unpack(">B", stream.read(1))[0]
deserialize_uint16_t  = lambda stream: struct.unpack(">H", stream.read(2))[0]
deserialize_uint32_t  = lambda stream: struct.unpack(">L", stream.read(4))[0]
deserialize_uint64_t  = lambda stream: struct.unpack(">Q", stream.read(8))[0]
deserialize_float32_t = lambda stream: struct.unpack(">f", stream.read(4))[0]
deserialize_float64_t = lambda stream: struct.unpack(">d", stream.read(8))[0]
deserialize_null_t    = lambda stream: None

deserialize_types = {
    SerializableBaseTypes.bool_t:      deserialize_bool_t,
    SerializableBaseTypes.int8_t:      deserialize_int8_t,
    SerializableBaseTypes.int16_t:     deserialize_int16_t,
    SerializableBaseTypes.int32_t:     deserialize_int32_t,
    SerializableBaseTypes.int64_t:     deserialize_int64_t,
    SerializableBaseTypes.uint8_t:      deserialize_uint8_t,
    SerializableBaseTypes.uint16_t:     deserialize_uint16_t,
    SerializableBaseTypes.uint32_t:     deserialize_uint32_t,
    SerializableBaseTypes.uint64_t:     deserialize_uint64_t,
    SerializableBaseTypes.float32_t:   deserialize_float32_t,
    SerializableBaseTypes.float64_t:   deserialize_float64_t,
    SerializableBaseTypes.null_t:      deserialize_null_t,
}

def deserialize_value(stream, **kwargs):

    """
    todo: allow passing a custom registry in as a kwarg
          for non-builtin types use the registry when decoding

    when serializing to persistent storage, store the registry
    as a sequence of typeid: string-name (using basic types)
    so that future versions can decode the file, assuming
    type ids change but names do not change.
    """
    buf = stream.read(2)
    if len(buf) != 2:
        raise SerializableHeaderError("unexpected end of stream")
    type_id, = struct.unpack(">H", buf)

    if 'registry' in kwargs:
        registry = kwargs['registry']
    else:
        registry = SerializableType.registry


    if type_id in deserialize_types:
        typ_ = deserialize_types[type_id]
    elif type_id in registry:
        typ_ = registry[type_id]
    else:
        raise SerializableHeaderError("invalid type_id: %d" % type_id)

    try:
        if type_id in deserialize_types:
            return deserialize_types[type_id](stream)
        elif type_id in registry:
            obj = registry[type_id]()
            obj.deserialize(stream, **kwargs)
            return obj
        else:
            raise ValueError("invalid type_id %d" % type_id)
    except SerializableHeaderError as e:
        # a subfield failed to deserialize
        # raise a new error with the last type that successfully decoded
        raise SerializableError("unable to deserialize type %s" % typ_)

def deserialize_string(stream):

    length = deserialize_value(stream)
    if not isinstance(length, int):
        raise TypeError("expected integer length, found %s" % type(length))

    if length > MAX_BYTES_LENGTH:
        raise ValueError("string length too large: %d" % length)

    return stream.read(length).decode("utf-8")

def deserialize_bytes(stream):

    length = deserialize_value(stream)

    if not isinstance(length, int):
        raise TypeError("expected integer length, found %s" % type(length))

    if length > MAX_BYTES_LENGTH:
        raise ValueError("string length too large: %d" % length)

    return stream.read(length)

def deserialize_map(stream):
    length = deserialize_value(stream)

    if not isinstance(length, int):
        raise TypeError("expected integer length, found %s" % type(length))

    if length > MAX_ARRAY_LENGTH:
        raise ValueError("map length too large: %d" % length)

    obj = {}
    for i in range(length):
        k = deserialize_value(stream)
        v = deserialize_value(stream)
        obj[k] = v

    return obj

def deserialize_seq(stream):
    length = deserialize_value(stream)

    if not isinstance(length, int):
        raise TypeError("expected integer length, found %s" % type(length))

    if length > MAX_ARRAY_LENGTH:
        raise ValueError("seq length too large: %d" % length)

    obj = []
    for i in range(length):

        try:
            o = deserialize_value(stream)
            obj.append(o)
        except Exception as e:
            raise e

    return obj

def deserialize_set(stream):
    length = deserialize_value(stream)

    if not isinstance(length, int):
        raise TypeError("expected integer length, found %s" % type(length))

    if length > MAX_ARRAY_LENGTH:
        raise ValueError("set length too large: %d" % length)

    obj = set([deserialize_value(stream) for i in range(length)])

    return obj

deserialize_types[SerializableBaseTypes.string_t] = deserialize_string
deserialize_types[SerializableBaseTypes.bytes_t] = deserialize_bytes
deserialize_types[SerializableBaseTypes.map_t] = deserialize_map
deserialize_types[SerializableBaseTypes.seq_t] = deserialize_seq
deserialize_types[SerializableBaseTypes.set_t] = deserialize_set

def deserialize_registry(stream, **kwargs):

    obj = {}
    length = deserialize_value(stream, **kwargs)
    for i in range(length):

        type_id = deserialize_value(stream, **kwargs)
        cls_name = deserialize_value(stream, **kwargs)

        obj[type_id] = SerializableType.names[cls_name]
    return obj

def _fromJsonBasic(type, field, value):
    if isinstance(type, SerializableType):
        inst = None
        if value is not None:
            inst = type.fromJson(value)
        return inst
    elif isinstance(type, SerializableEnumType):
        return type(type.fromJson(value))
    elif hasattr(type, 'fromJson'):
        return type.fromJson(value)
    else:
        origin = get_origin(type)
        # cast the type, to allow for integer mappings
        # that can be round-tripped through a json representation
        if origin:
            return origin(value)
        else:
            return type(value)

def _toJsonBasic(type, field, value):

    if isinstance(type, SerializableType):
        return value.toJson()
    elif hasattr(type, 'toJson'):
        return type(value).toJson()
    else:
        return value

class Serializable(object, metaclass=SerializableType):
    """ Base class for defining a new serializable class. Sub Classes of
    Serializable can be converted to and from byte representations as well
    as JSON string representations.

    :attr type_id: Automatically assigned unique type identifier for this class/instance.
    type_id is a special attribute which can be set in the class definition
    to override the type_id used for the class. Values less than 256 are
    reserverd for use by MpGameServer.
    """

    def __init__(self, **kwargs):
        for attr, t in self.__annotations__.items():
            if isinstance(t, Serializable) or \
               t in (dict, list, set, tuple):
                setattr(self, attr, t())
            elif get_origin(t) in (dict, list, set, tuple):
                setattr(self, attr, get_origin(t)())

        for k,v in kwargs.items():
            if k in self._fields:
                setattr(self, k, v)

    def __repr__(self):
        values = ["%r:%r" % (f, getattr(self, f)) for f in self._fields]
        return "%s({%s})" % (self.__class__.__name__, ", ".join(values))

    def serialize_header(self, stream):

        """ Writes a header to the stream


        :param stream: a file like object opened for writing bytes to.

        """
        stream.write(struct.pack(">H", self.type_id))

    def serialize(self, stream, **kwargs):

        """ Write the content of this class to the stream


        :param stream: a file like object opened for writing bytes to.

        """
        #stream.write(struct.pack(">H", self.type_id))
        for field in self._fields:
            serialize_value(stream, getattr(self, field))

    def deserialize(self, stream, **kwargs):
        """populate member attributes by reading fields from a stream.

        :param stream: a file like object opened for reading bytes from.
        :param kwargs: extra arguments that are passed to deserialize, a specialization of deserialize
        can use kwargs to control how the class is deserialized

        """
        for field in self._fields:
            setattr(self, field, deserialize_value(stream))
        return self

    def dumpb(self, **kwargs):
        """ return a byte array representation of this class

        :param kwargs: extra arguments that are passed to deserialize, a specialization of deserialize
        can use kwargs to control how the class is deserialized

        """
        stream = BytesIO()
        stream.write(struct.pack(">H", self.type_id))
        self.serialize(stream, **kwargs)
        return stream.getvalue()

    def dumps(self, indent=None, sort_keys=False, **kwargs):
        return json.dumps(self.toJson(), indent=indent, sort_keys=sort_keys, **kwargs)

    def dumpz(self, **kwargs):
        """ private get a compressed byte representation
        """
        stream = BytesIO()
        wrapper = gzip.open(stream, "wb")
        self.serialize_header(wrapper)
        self.serialize(wrapper, **kwargs)
        wrapper.close()
        return stream.getvalue()

    @staticmethod
    def loadb(stream, **kwargs):
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
        return deserialize_value(stream, **kwargs)

    @staticmethod
    def loadz(stream, **kwargs):
        """ private load from a compressed stream
        """
        if isinstance(stream, bytes):
            stream = BytesIO(stream)
        with gzip.open(stream, "rb") as wrapper:
            return deserialize_value(wrapper, **kwargs)

    @classmethod
    def loads(cls, string, **kwargs):
        return cls.fromJson(json.loads(string, **kwargs))

    @classmethod
    def fromJson(cls, record):
        """ initialize a new instance of Type from a JSON object

        Uses the type annotations for members of Type to determine how
        to convert the JSON object attributes into member attributes

        This will recursivley convert child attributes made up of
        iterable and mapping types.

        Invalid keys in the given record are ignored.

        :param cls: the class instance
        :param record: a JSON object
        """

        inst = cls()

        for field in inst._fields:

            if field in record:
                origin = get_origin(inst.__annotations__[field])
                if origin is not None:
                    args = get_args(inst.__annotations__[field])

                    if origin is list and isinstance(record[field], (Iterable, Sequence)):
                        lst = []
                        for rec in record[field]:
                            lst.append(_fromJsonBasic(args[0], field, rec))
                        setattr(inst, field, lst)
                    elif origin is set and isinstance(record[field], (Iterable, Sequence)):
                        lst = []
                        for rec in record[field]:
                            lst.append(_fromJsonBasic(args[0], field, rec))
                        setattr(inst, field, set(lst))
                    elif origin is dict and isinstance(record[field], Mapping):
                        map = {}
                        for key,val in record[field].items():
                            k = _fromJsonBasic(args[0], field, key)
                            v = _fromJsonBasic(args[1], field, val)
                            map[k] = v
                        setattr(inst, field, map)
                    elif origin is tuple and isinstance(record[field], (Iterable, Sequence)):
                        lst = []
                        for i, t in enumerate(args):
                            if i < len(record[field]):
                                v = record[field][i]
                                lst.append(_fromJsonBasic(t, field, v))
                            else:
                                # for missing values pad the tuple with null values
                                lst.append(None)
                        setattr(inst, field, tuple(lst))
                    elif record[field] is None:
                        setattr(inst, field, None)
                    else:
                        raise TypeError("%s != %s" % (origin, type(record[field])))
                else:
                    setattr(inst, field, _fromJsonBasic(
                        inst.__annotations__[field], field, record[field]))
        return inst

    def toJson(self):

        """ return a JSON object representation of this class

        JSON uses a limited subset of valid python types. In particular,
        the following transforms are performed:

        1. dictionary keys are converted to strings.
           the key type must accept converting a string representation back
           to the native typein order for a round trip through Serializable.fromJson
           to work correctly. SerializableEnum can be used as a key in a dictionary,
           as can integers.
        2. SerializableEnum are converted to a string representation
        3. List/Set/Tuple are all converted to a list. With proper type annotation hints,
           these types can all be correctly round-tripped with Serializable.fromJson.

        In addition, no conversion is done for float types. This means that invalid
        JSON float values are not modified.
        """

        obj = {}
        for field in self._fields:

            origin = get_origin(self.__annotations__[field])
            if origin is not None:
                args = get_args(self.__annotations__[field])

                record = getattr(self, field)
                if origin is list and isinstance(record, (Iterable, Sequence)):
                    lst = []
                    for tmp in record:
                        lst.append(_toJsonBasic(args[0], field, tmp))
                    obj[field] = lst

                elif origin is set and isinstance(record, (Iterable, Sequence)):
                    lst = []
                    for tmp in record:
                        lst.append(_toJsonBasic(args[0], field, tmp))
                    obj[field] = lst

                elif origin is dict and isinstance(record, Mapping):
                    map = {}
                    for key, val in record.items():
                        k = _toJsonBasic(args[0], field, key)
                        v = _toJsonBasic(args[1], field, val)
                        map[k] = v
                    obj[field] = map

                elif origin is tuple and isinstance(record, (Iterable, Sequence)):
                    lst = []
                    for i, t in enumerate(args):
                        if i < len(record):
                            lst.append(_toJsonBasic(t, field, record[i]))
                        else:
                            lst.append(None)

                    obj[field] = lst
                elif record is None:
                    obj[field] = None

                else:
                    raise TypeError("%s != %s" % (origin, type(record)))

            else:
                obj[field] = _toJsonBasic(self.__annotations__[field],
                    field, getattr(self, field))
        return obj

class SerializableEnumType(type):
    _enums = {}

    def __new__(metacls, name, bases, namespace):
        cls = super().__new__(metacls, name, bases, namespace)
        if name == 'SerializableEnum':
            return cls
        # allow a user to specify exactly the type_id in the class def
        # or generate a new type_id when one is not defined.
        parent_type = cls.mro()[1]
        if not hasattr(cls, 'type_id') or parent_type.type_id == cls.type_id:
            if cls.__module__ in SerializableType.custom_id:
                cls.type_id = SerializableType.custom_id[cls.__module__]
                SerializableType.custom_id[cls.__module__] += 1
            else:
                cls.type_id = SerializableType.next_type_id
                SerializableType.next_type_id += 1

        SerializableType.registry[cls.type_id] = cls
        SerializableType.names[cls.__name__] = cls

        cls._value2name = {}
        cls._name2value = {}
        SerializableEnumType._enums[cls.__name__] = cls

        for name in dir(cls):
            if ispublic(cls, name):

                cls._value2name[getattr(cls, name)] = name
                cls._name2value[name] = getattr(cls, name)
                # wrap the value types as instances of enum
                setattr(cls, name, cls(getattr(cls, name)))
        return cls

class SerializableEnum(object, metaclass=SerializableEnumType):
    """
    SerializableEnum is a reimplementation of Python's Enum with support for use in a Serializable.

    A SerializableEnum can be used as part of a Generic specifier, for either typing.List or typing.Tuple
    as well as either a key or value in typing.Dict

    :attr value: get the underlying value of the enum
    """

    def __init__(self, value=None):
        if isinstance(value, self.__class__):
            self.value = value.value
        elif value in self.__class__._value2name:
            self.value = value
        elif value is None:
            self.value = value
        else:
            self.value = value
            raise ValueError(value)

    def __repr__(self):
        return "%s.%s" % (self.__class__.__name__, self._value2name[self.value])

    def __str__(self):
        return "%s.%s" % (self.__class__.__name__, self._value2name[self.value])

    def serialize_header(self, stream):

        """


        :param stream: a file like object opened for writing bytes to.

        """
        stream.write(struct.pack(">H", self.type_id))

    def serialize(self, stream, **kwargs):
        """ write the current value to a stream

        :param stream: a file like object opened for writing bytes to.
        """
        #stream.write(struct.pack(">H", self.type_id))
        if self.value not in self._value2name:
            raise ValueError("Illegal enum value: %s" % self.value)
        serialize_value(stream, self.value)

    def deserialize(self, stream, **kwargs):
        """
        :param stream: a file like object opened for writing bytes to.

        """
        self.value = deserialize_value(stream, **kwargs)
        return self

    def name(self):
        """ return a string representation of the enum value """
        return self.__class__._value2name[self.value]

    @classmethod
    def fromJson(cls, value):
        return cls._name2value[value]

    def toJson(self):
        """ return a dictionary suitable for passing to json.dumps
        """
        return self.__class__._value2name[self.value]

    def __lt__(self, other):
        return self.value < other.value

    def __le__(self, other):
        return self.value <= other.value

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return self.value != other.value

    def __ge__(self, other):
        return self.value >= other.value

    def __gt__(self, other):
        return self.value > other.value

    def __hash__(self):
        return hash(self.value)

    def __bool__(self):
        return bool(self.value)

def main():  #pragma: no cover
    pass

if __name__ == '__main__':  #pragma: no cover
    main()