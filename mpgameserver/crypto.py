#! cd .. && python3 -m mpgameserver.crypto

"""

MpGameServer uses the [Cryptography](https://cryptography.io) library to implement security.
Algorithms used by MpGameServer include: Elliptic Curve Diffie-Hellman (ECDH) is used for key exchange;
Elliptic Curve Digital Signature Algorithm (ECDSA) is used for digital signatures;
Hash-based essage authentication code for Key Derivation Function (HKDF) is used to derive keys;
AES-GCM is used to encrypt traffic;
SHA-256 is used as the default hashing algorithm.
The default Elliptic Curve used is SECP256R1 also known as NIST P-256.

[ECDH](https://en.wikipedia.org/wiki/Elliptic-curve_Diffie%E2%80%93Hellman): Elliptic Curve Diffie-Hellman is an algorithm for exhanging a secret key over an untrusted network.
Both parties generate a private key and share the public key with each other. From there a shared
secret can be derived.

[ECDSA](https://en.wikipedia.org/wiki/Elliptic_Curve_Digital_Signature_Algorithm): Elliptic Curve Digital Signature Algorithm is an algorthim for signing and verifying data.
A private key is used to sign a piece of data (a byte array) and produce a signature (also a byte array)
A public key can then be used to verify that a given signature matches the given data. When the
public key is shared through a separate channel (or pre-shared) then this method can be used
to authenticate that a given piece of data was received from a host controlling the private key
as well as verify the integrity that the data was not modified.

ECDH should be combined with ECDSA when possible to prevent a man in the midle attack.
MpGameServer uses a pre-shared root public key to verify sensitive data from the server.
When a new session is created a new key pair is generated and the public key is signed
with the root private key. This allows the client to verify that the public key
originated from the correct server. An HKDF is then used to derive the AES key used to encrypt
traffic between the client and server

> :information_source: Because ECDH is difficult to implement correctly, it is not exposed as a public api.

SECP256R1 (also known as NIST P-256) is not listed as a safe curve.
More information can be found here: https://safecurves.cr.yp.to/.
The cryptography library currently does not implement any safe curves.
However there are no known practical attacks against this curve at this time.
It is considered safe for non-sensitive information

[AES-GCM](https://en.wikipedia.org/wiki/Galois/Counter_Mode): Advanced Encryption Standard - Galois Counter Mode.
Is an encryption and decryption algorithm which allows for authenticated encryption.
Data encrypted with AES-GCM includes a tag which can be verified before decryption.
This provides both data integrity (meaning an attacker cannot modify the cipher test) and confidentiality (meaning an attacker
will not be able to extract information from the cipher text)

The public api cryptography in MpGameServer provides two classes to help with managing private and public keys
"""
import os
import time
import binascii
import argparse
import select

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESCCM, ChaCha20Poly1305
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.algorithms import AES
from cryptography.hazmat.primitives.ciphers.modes import CTR
from cryptography.hazmat.primitives.hmac import HMAC
from cryptography.hazmat.primitives.constant_time import bytes_eq
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.serialization import Encoding, \
    PrivateFormat, PublicFormat, NoEncryption, \
    load_der_public_key, load_der_private_key, \
    load_pem_private_key, load_pem_public_key

from cryptography.hazmat.backends.openssl.ec import _EllipticCurvePublicKey, _EllipticCurvePrivateKey

def public_key_repr(self):
    b = self.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return "<PublicKey:'%s'>" % binascii.hexlify(b).decode("utf-8")

def private_key_repr(self):
    b = self.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    return "<PrivateKey:'%s'>" % binascii.hexlify(b).decode("utf-8")

# monkey patch the key classes we are using for pretty printing
_EllipticCurvePublicKey.__repr__ = public_key_repr
_EllipticCurvePrivateKey.__repr__ = private_key_repr

ENCRYPTION_KEY_LENGTH = 16
ENCRYPTION_SALT_LENGTH = 16
ENCRYPTION_TAG_LENGTH = 16
ENCRYPTION_IV_LENGTH = 12

def crc32(data):
    """ compute 32-bit checksum
    """
    return binascii.crc32(data) & 0xFFFFFFFF

def encrypt_gcm(key, iv, aad, data):
    """
    encrypt and sign using AES-GCM

    This method appends a 16 byte signature to the end of the ciphertext

    key: 16 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt

    """
    return AESGCM(key).encrypt(iv, data, aad)

def decrypt_gcm(key, iv, aad, data):
    """
    verify and decrypt using AES-GCM

    key: 16 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt
    """
    return AESGCM(key).decrypt(iv, data, aad)

def encrypt_ccm(key, iv, aad, data):
    """
    encrypt and sign using AES-CCM

    This method appends a 16 byte signature to the end of the ciphertext

    In testing this is slightly slower than GCM mode

    key: 16 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt

    """
    return AESCCM(key).encrypt(iv, data, aad)

def decrypt_ccm(key, iv, aad, data):
    """
    verify and decrypt using AES-CCM

    key: 16 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt
    """
    return AESCCM(key).decrypt(iv, data, aad)

def encrypt_chacha20(key, iv, aad, data):
    """ encrypt and tag using ChaCha20

    This method appends a 16 byte signature to the end of the ciphertext

    key: 32 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt

    """
    return ChaCha20Poly1305(key).encrypt(iv, data, aad)

def decrypt_chacha20(key, iv, aad, data):
    """ decrypt and verify using ChaCha20

    key: 16 byte key
    iv: 12 bytes iv
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plain text to encrypt

    """
    return ChaCha20Poly1305(key).decrypt(iv, data, aad)

def encrypt_ctr(key, iv, aad, data):
    """
    encrypt using CTR then sign with an HMAC

    Note: this implementation is similar to AES-CCM, but is slower.
    The implementation is left in only for benchmarking purposes.

    Note: in theory this should parallize well, however in practice
    it is about 2x slower than GCM mode. The HMAC is not the bottleneck

    key: 16 byte key
    iv: 12 bytes nonce. 4 zero bytes are appended to create the 16 byte
        nonce used for CTR mode
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plaint text to encrypt

    future work: require key to be 32 bytes, and then use
        16 bytes for the HMAC and the other 16 bytes for CTR mode
    """
    nonce = iv + b'\x00\x00\x00\x00'

    encryptor = Cipher(AES(key), CTR(nonce),
        backend=default_backend()).encryptor()

    ct = encryptor.update(data) + encryptor.finalize()

    h = HMAC(key, SHA256(), backend=default_backend())
    h.update(aad)
    h.update(ct)
    tag = h.finalize()[:16]

    return ct + tag

def decrypt_ctr(key, iv, aad, data):
    """
    verify HMAC and decrypt using CTR mode

    key: 16 byte key
    iv: 12 bytes nonce. 4 zero bytes are appended to create the 16 byte
        nonce used for CTR mode
    aad: bytes. additional unencrypted data to include in the signature
    data: bytes. plaint text to encrypt

    """
    nonce = iv + b'\x00\x00\x00\x00'
    ct = data[:-16]
    tag = data[-16:]

    h = HMAC(key, SHA256(), backend=default_backend())
    h.update(aad)
    h.update(ct)
    act = h.finalize()[:16]

    if not bytes_eq(tag, act):
        raise ValueError()

    decryptor = Cipher(AES(key), CTR(nonce),
        backend=default_backend()).decryptor()

    return decryptor.update(ct) + decryptor.finalize()

class EllipticCurvePrivateKey(object):
    """ A Elliptic Curve Private key used for key exchange and signing

    This class implements methods for performing basic Elliptic Curve operations,
    such as converting between common file formats and signing data.

    """
    def __init__(self, key=None):
        super(EllipticCurvePrivateKey, self).__init__()

        self.key = key

    def __repr__(self):
        return private_key_repr(self.key)

    def curve(self):
        return self.key.curve

    def getBytes(self):
        return self.key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())

    def getPrivateKeyPEM(self):
        return self.key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode("utf-8")

    def getPublicKey(self):

        return EllipticCurvePublicKey(self.key.public_key())

    def savePEM(self, path):
        with open(path, "w") as wf:
            wf.write(self.getPrivateKeyPEM())

    def sign(self, data):
        """ returns a signature for the supplied data
        """
        return self.key.sign(data, ec.ECDSA(hashes.SHA256()))

    @staticmethod
    def new():
        key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        return EllipticCurvePrivateKey(key)

    @staticmethod
    def fromPEM(pem: str):
        return EllipticCurvePrivateKey(
            load_pem_private_key(pem.encode("utf-8"),
                password=None, backend=default_backend()))

    @staticmethod
    def fromBytes(der: bytes):
        return EllipticCurvePrivateKey(
            load_der_private_key(der,
                password=None, backend=default_backend()))

class EllipticCurvePublicKey(object):
    """ A Elliptic Curve Private key used for key exchange and signing

    This class implements methods for performing basic Elliptic Curve operations,
    such as converting between common file formats and verifying signed data.

    :attr InvalidSignature: exception type raised by verify when signature is invalid
    """

    InvalidSignature = InvalidSignature

    def __init__(self, key):
        super(EllipticCurvePublicKey, self).__init__()
        self.key = key

    def __repr__(self):
        return public_key_repr(self.key)

    def curve(self):
        return self.key.curve

    def x(self) -> bytes:
        return self.key.public_numbers().x.to_bytes(32, 'little')

    def y(self) -> bytes:
        return self.key.public_numbers().y.to_bytes(32, 'little')

    def compress(self) -> bytes:
        """
        compress elliptic curve public key as defined in ANSI X9.62 section 4.3.6
        """
        return self.key.public_bytes(Encoding.X962, PublicFormat.CompressedPoint)

    def getEncryptionKey(self):
        sha = hashlib.sha256()
        sha.update(self.x())
        sha.update(self.y())
        return sha.digest()

    def getBytes(self):
        return self.key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)

    def getPublicKeyPEM(self):
        return self.key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode("utf-8")

    def savePEM(path):
        with open(path, "w") as wf:
            wf.write(self.getPublicKeyPEM())

    def verify(self, signature, data):
        """ validate that the supplied data matches a signature

        raises an InvalidSignature exception on error
        """
        self.key.verify(signature, data, ec.ECDSA(hashes.SHA256()))

    @staticmethod
    def fromPEM(pem: str):
        return EllipticCurvePublicKey(
            load_pem_public_key(pem.encode("utf-8"),
                backend=default_backend()))

    @staticmethod
    def fromBytes(der: bytes):
        return EllipticCurvePublicKey(
            load_der_public_key(der,
                backend=default_backend()))

    @staticmethod
    def uncompress(curve: ec.EllipticCurve, data: bytes):
        """
        load a compressed elliptic curve
        """
        key = ec.EllipticCurvePublicKey.from_encoded_point(curve, data)
        return EllipticCurvePublicKey(key)



"""

ECDH: Elliptic Curve Diffie-Hellman

Step 1:
    - client generates private key
    - send public key to server
Step 2:
    - server generates private key and salt
    - derives shared secret
    - sends public key to client along with the salt
Step 3:
    - client derives shared secret using same salt

"""

def ecdh_server(server_private_key, client_public_key):
    """ Step 2: derive shared secret on the server """

    salt = os.urandom(ENCRYPTION_SALT_LENGTH)

    shared_secret = server_private_key.key.exchange(ec.ECDH(), client_public_key.key)

    # info is a string which uniquely describes this data link
    # the format is:
    #  {version}-{ec-alg}-{md-alg}-{encryption-alg}-{server-id}-{client-id}

    derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=ENCRYPTION_KEY_LENGTH,
            salt=salt,
            info=b'01-secp256r1-sha256-aesgcm128-server-client',
            backend=default_backend()
        ).derive(shared_secret)

    return salt, derived_key

def ecdh_client(client_private_key, server_public_key, salt):
    """ Step 3: derive shared secret on the client """

    shared_secret = client_private_key.key.exchange(ec.ECDH(), server_public_key.key)

    # info is a string which uniquely describes this data link
    # the format is:
    #  {version}-{ec-alg}-{md-alg}-{encryption-alg}-{server-id}-{client-id}
    derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=ENCRYPTION_KEY_LENGTH,
            salt=salt,
            info=b'01-secp256r1-sha256-aesgcm128-server-client',
            backend=default_backend()
        ).derive(shared_secret)

    return derived_key

def _loadKeyFromFile(file_stream):
    """
    file_stream: sys.stdin
    """
    key = None
    if not file_stream.isatty():
        r, _, _ = select.select([file_stream], [], [], 0)
        if r:
            key = EllipticCurvePrivateKey.fromPEM(file_stream.read())
    return key

"""
ECC Asymmetric Encryption

https://cryptobook.nakov.com/asymmetric-key-ciphers/ecc-encryption-decryption


"""

def ecc_asym_encrypt_key(publicKey: EllipticCurvePublicKey) -> (bytes, bytes):
    """

    Derive a new shared secret key using a given public key.
    The key can be used by a peer to encrypt a message that can only
    be decrypted by the owner of the corresponding private key.
    The return value is the new shared secret key and the peer public key
    which can be used to derive the shared secret key again.


    public_key: an ecc public key
    returns a 2-tuple (shared_key, compressed_public_key)
    """
    peer_key = EllipticCurvePrivateKey.new()
    shared_key = peer_key.key.exchange(ec.ECDH(), publicKey.key)
    return (shared_key, peer_key.getPublicKey().compress())

def ecc_asym_decrypt_key(privateKey: EllipticCurvePrivateKey, peerCompressedPublicKey: bytes) -> bytes:

    """
    Derive a shared secret using the private key and a compressed peer
    public key. The inputs to this function are the corresponding private
    key to the public key given to ecc_asym_encrypt_key, and the public
    key that that function returns.

    """
    peer_pubkey = EllipticCurvePublicKey.uncompress(
        ec.SECP256R1(), peerCompressedPublicKey)

    return privateKey.key.exchange(ec.ECDH(), peer_pubkey.key)

def main():

    key = EllipticCurvePrivateKey.new()
    pub = key.getPublicKey()

    print(pub.curve())
    print(pub.getEncryptionKey())
    print("-----------")
    shared_key1, peer_pubkey = ecc_asym_encrypt_key(pub)
    shared_key2 = ecc_asym_decrypt_key(key, peer_pubkey)
    print(binascii.hexlify(shared_key1))
    print(binascii.hexlify(shared_key2))

if __name__ == '__main__':
    main()