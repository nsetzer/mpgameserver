
import unittest
from mpgameserver import crypto
import binascii

class CryptoTestCase(unittest.TestCase):

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

    def test_crc(self):
        data = b"OrpheanBeholderScryDoubt"

        self.assertEqual(crypto.crc32(data), 0x49480567)

    def test_gcm(self):

        key  = b"0" * 16
        iv   = b"0" * 12
        aad  = b"unencrypted"
        data = b"encrypted"

        ct = crypto.encrypt_gcm(key, iv, aad, data)
        pt = crypto.decrypt_gcm(key, iv, aad, ct)

        self.assertEqual(data, pt)


    def test_ccm(self):

        key  = b"0" * 16
        iv   = b"0" * 12
        aad  = b"unencrypted"
        data = b"encrypted"

        ct = crypto.encrypt_ccm(key, iv, aad, data)
        pt = crypto.decrypt_ccm(key, iv, aad, ct)

        self.assertEqual(data, pt)

    def test_ctr(self):

        key  = b"0" * 16
        iv   = b"0" * 12
        aad  = b"unencrypted"
        data = b"encrypted"

        ct = crypto.encrypt_ctr(key, iv, aad, data)
        pt = crypto.decrypt_ctr(key, iv, aad, ct)

        self.assertEqual(data, pt)

    def test_chacha20(self):

        key  = b"0" * 32
        iv   = b"0" * 12
        aad  = b"unencrypted"
        data = b"encrypted"

        ct = crypto.encrypt_chacha20(key, iv, aad, data)
        pt = crypto.decrypt_chacha20(key, iv, aad, ct)

        self.assertEqual(data, pt)

    def test_private_key_pem(self):

        key = crypto.EllipticCurvePrivateKey.new()
        pem = key.getPrivateKeyPEM()

        key2 = crypto.EllipticCurvePrivateKey.fromPEM(pem)

        self.assertEqual(key.getBytes(), key2.getBytes())

    def test_private_key_der(self):

        key = crypto.EllipticCurvePrivateKey.new()
        der = key.getBytes()

        key2 = crypto.EllipticCurvePrivateKey.fromBytes(der)

        self.assertEqual(key.getBytes(), key2.getBytes())

    def test_public_key_pem(self):

        key = crypto.EllipticCurvePrivateKey.new().getPublicKey()
        pem = key.getPublicKeyPEM()

        key2 = crypto.EllipticCurvePublicKey.fromPEM(pem)

        self.assertEqual(key.getBytes(), key2.getBytes())

    def test_public_key_der(self):

        key = crypto.EllipticCurvePrivateKey.new().getPublicKey()
        der = key.getBytes()

        key2 = crypto.EllipticCurvePublicKey.fromBytes(der)

        self.assertEqual(key.getBytes(), key2.getBytes())

    def test_ecdh(self):

        client_key = crypto.EllipticCurvePrivateKey.new()
        server_key = crypto.EllipticCurvePrivateKey.new()

        salt, server_derived = crypto.ecdh_server(server_key, client_key.getPublicKey())


        client_derived = crypto.ecdh_client(client_key, server_key.getPublicKey(), salt)

        self.assertEqual(server_derived, client_derived)

    def test_ecdsa(self):

        key = crypto.EllipticCurvePrivateKey.new()

        data = b"OrpheanBeholderScryDoubt"
        signature = key.sign(data)

        key.getPublicKey().verify(signature, data)

    def test_ecc_asym(self):
        key = crypto.EllipticCurvePrivateKey.new()
        shared_key1, peer_pubkey = crypto.ecc_asym_encrypt_key(key.getPublicKey())
        shared_key2 = crypto.ecc_asym_decrypt_key(key, peer_pubkey)


        str1 = binascii.hexlify(shared_key1)
        str2 = binascii.hexlify(shared_key2)

        self.assertEqual(str1, str2)

def main():
    unittest.main()


if __name__ == '__main__':
    main()
