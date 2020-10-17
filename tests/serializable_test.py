
import unittest
from typing import NewType, Generic, List, Dict, Tuple, Set, get_args, get_origin
from mpgameserver import serializable
from mpgameserver.serializable import SerializableType, Serializable, SerializableEnum
from io import BytesIO
import struct

class BasicTypes(Serializable):
    v1: int = 0
    v2: float = 0
    v3: str = ""
    v4: bool = False

class User(Serializable):
    username: str = ""
    password: str = ""

class Users(Serializable):
    users: List[User] = None

class Color(SerializableEnum):
    RED=1
    GREEN=2
    BLUE=3

class ColorMap(Serializable):
    cfg: Dict[Color,int] = None

class Position(Serializable):
    pos: Tuple[int, int] = None

class ColorSet(Serializable):
    colors: Set[Color] = None

# additional structs with a custom type_id
SerializableType.setRootId(__name__, 1024)
class NoAnnoStruct(Serializable):
    v0 = 0
class NoAnnoEnum(SerializableEnum):
    A=1
    B=2

class SerializableTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        super().setUp()

    def tearDown(self):
        super().tearDown()

    def test_serialize_basic_types(self):

        msg = BasicTypes(v1=123,v2=3.14,v3="abc",v4=True)

        payload = msg.dumpb()

        msg2 = Serializable.loadb(payload)

        self.assertEqual(msg.v1, msg2.v1)
        self.assertEqual(msg.v3, msg2.v3)
        self.assertEqual(msg.v4, msg2.v4)
        self.assertTrue(abs(msg.v2 - msg2.v2) < 1e-6)

    def test_serialize_seq(self):

        msg = Users(users=[User(username='test')])

        payload = msg.dumpb()

        msg2 = Serializable.loadb(payload)

        self.assertEqual(msg.users[0].username, msg2.users[0].username)

    def test_serialize_map(self):

        msg = ColorMap(cfg={Color.RED:123})

        payload = msg.dumpb()

        msg2 = Serializable.loadb(payload)

        self.assertEqual(msg.cfg[Color.RED], msg2.cfg[Color.RED])

    def test_serialize_tuple(self):

        msg = Position(pos=(32,64))

        payload = msg.dumpb()

        msg2 = Serializable.loadb(payload)

        self.assertEqual(msg.pos[0], msg2.pos[0])

    def test_serialize_set(self):

        msg = ColorSet(colors=set([Color.BLUE, Color.GREEN]))

        payload = msg.dumpb()

        msg2 = Serializable.loadb(payload)

        self.assertTrue(Color.BLUE in msg2.colors)
        self.assertTrue(Color.GREEN in msg2.colors)

    def test_serialize_enum(self):

        self.assertTrue(Color.RED < Color.BLUE)
        self.assertTrue(Color.RED <= Color.BLUE)

        self.assertTrue(Color.BLUE > Color.RED)
        self.assertTrue(Color.BLUE >= Color.RED)

        if not Color.RED:
            self.fail("not truthy")

        self.assertEqual(Color.RED.name(), "RED")
        self.assertEqual(str(Color.RED), "Color.RED")
        self.assertEqual(repr(Color.RED), "Color.RED")

        with self.assertRaises(ValueError):
            Color(1024)

    def test_json_basic(self):

        user = {"username": "test", "password": "test"}

        msg = User.fromJson(user)

        self.assertEqual(user['username'], msg.username)

        obj = msg.toJson()
        self.assertEqual(user, obj)

    def test_json_generic_list(self):

        users = {'users':[{"username": "test", "password": "test"}]}

        msg = Users.fromJson(users)

        self.assertEqual(users['users'][0]['username'], msg.users[0].username)

        obj = msg.toJson()
        self.assertEqual(users, obj)

    def test_json_generic_map(self):

        cfg = {'cfg': {'RED': 123, 'BLUE': 456}}

        msg = ColorMap.fromJson(cfg)

        self.assertEqual(cfg['cfg']['RED'], msg.cfg[Color.RED])

        obj = msg.toJson()
        self.assertEqual(cfg, obj)

    def test_json_generic_tuple(self):

        pos = {'pos': (32,64)}

        msg = Position.fromJson(pos)

        self.assertEqual(len(msg.pos), 2)
        self.assertEqual(msg.pos[0], 32)
        self.assertEqual(msg.pos[1], 64)

        obj = msg.toJson()
        self.assertEqual(pos['pos'][0], obj['pos'][0])
        self.assertEqual(pos['pos'][1], obj['pos'][1])

    def test_json_generic_tuple_short(self):

        pos = {'pos': (32,)}

        msg = Position.fromJson(pos)

        self.assertEqual(len(msg.pos), 2)
        self.assertEqual(msg.pos[0], 32)
        self.assertEqual(msg.pos[1], None)
        #self.assertEqual(pos['pos'][0], msg.pos[0])

        obj = msg.toJson()
        self.assertEqual(obj['pos'][0], 32)
        self.assertEqual(obj['pos'][1], None)

    def test_json_generic_set(self):

        colors = {'colors': ['BLUE', 'GREEN']}

        msg = ColorSet.fromJson(colors)

        self.assertTrue(Color.BLUE in msg.colors)
        self.assertTrue(Color.GREEN in msg.colors)

        obj = msg.toJson()
        self.assertTrue('BLUE' in obj['colors'])
        self.assertTrue('GREEN' in obj['colors'])
        self.assertTrue(isinstance(obj['colors'], list))

    def test_json_null(self):

        colors = {'colors': None}
        msg = ColorSet.fromJson(colors)
        self.assertEqual(msg.colors, None)

    def test_compressed_encode(self):

        user = User(username="admin", password="admin")

        enc = user.dumpz()

        user2 = User.loadz(enc)
        self.assertEqual(user.username, user2.username)

    def test_string_encode(self):

        user = User(username="admin", password="admin")

        enc = user.dumps()

        user2 = User.loads(enc)
        self.assertEqual(user.username, user2.username)

    def test_string_repr(self):

        user = User(username="admin", password="admin")

        # order is quaranteed using the order of fields
        self.assertEqual(repr(user),
            "User({'username':'admin', 'password':'admin'})")

    def test_registry_1(self):

        stream = BytesIO()
        serializable.serialize_registry(stream)

        stream.seek(0)

        registry = serializable.deserialize_registry(stream)

        for type_id, cls in registry.items():
            self.assertEqual(cls, SerializableType.registry[type_id])

    def test_registry_2(self):

        stream = BytesIO()
        user = User(username="admin", password="admin")

        custom_id = 12345

        stream.write(struct.pack(">H", custom_id))
        user.serialize(stream)

        stream.seek(0)

        registry = {custom_id: User}

        with self.assertRaises(serializable.SerializableHeaderError) as e:
            user2 = serializable.deserialize_value(stream)

        stream.seek(0)

        user2 = serializable.deserialize_value(stream, registry=registry)

        self.assertEqual(user.username, user2.username)

    def test_module_id(self):

        self.assertEqual(NoAnnoStruct.type_id, 1024)
        self.assertEqual(NoAnnoEnum.type_id, 1025)

#class Test(Serializable):
#    test: Dict[int, int] = None

def main():
    unittest.main()


if __name__ == '__main__':
    main()
