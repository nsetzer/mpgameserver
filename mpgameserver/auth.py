
import os
import time
import base64
import struct
from cryptography.hazmat.primitives.kdf import scrypt
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives import hashes

class Auth(object):
    """ Password hashing and verification

    Note: Both hashing and verifying passwords are expensive operations,
    taking around .1 to .2 seconds. The server event handler should use a TaskPool to run the
    authentication in a background process and handle the result asynchronously.

    Note: this does not encrypt the password. Theoretically, it is not possible to reverse
    the hash to recover the given password.

    :attr SALT_LENGTH: The length of the salt generated when hashing. 16 bytes.
    :attr DIGEST_LENGTH: The length of the generated hash. 24 bytes.
    """
    SALT_LENGTH=16
    DIGEST_LENGTH=24

    def __init__(self):  # pragma: no cover
        """ private """
        super(Auth, self).__init__()

        raise RunTimeError("%s cannot be instantiated" % self.__class__.__name__)

    @staticmethod
    def hash_password(password: bytes) -> str:
        """ hash a password

        :return: the hashed password

        The output string contains the parameters used to define the hash, as well
        as the randomly generated salt used.

        Implementation notes: This method pre-hashes the password using sha-256.
        A salt is generated and then it then hashes the output using
        scrypt with parameters N=16384, r=16, p=1.

        :param password: the user supplied password encoded as bytes

        """

        if not isinstance(password, bytes):
            raise TypeError("expected bytes received %s" % type(password))

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(password)
        key_material = digest.finalize()

        # N: iteration count
        # r: block size
        # p: parallelism factor
        # Memory required = 128 * N * r * p bytes
        # Memory required = 128 * 16384 * 16 * 1 bytes
        # Memory required = 33554432 bytes
        # Memory required = 32768 KB
        # Memory required = 32.0 MB
        N=16384
        r=16
        p=1
        salt = os.urandom(Auth.SALT_LENGTH)

        params = struct.pack(">HBBBB", N, r, p,
            Auth.SALT_LENGTH, Auth.DIGEST_LENGTH)

        # format:
        #  method:version:params:salt+hash


        header = b"scrypt:1:" + base64.b64encode(params) + b":"

        kdf = scrypt.Scrypt(salt, Auth.DIGEST_LENGTH, N, r, p,
            backend=default_backend())
        out = kdf.derive(key_material)

        footer = base64.b64encode(salt + out)

        return (header + footer).decode("utf-8")

    @staticmethod
    def verify_password(password: bytes, password_hash: str) -> bool:
        """ verify a given password matches the given password hash

        raises TypeError, ValueError if the input is not well formed

        returns True if the password matches the hash. otherwise False

        The output of hash_password contains the parameters and salt as well
        as the hashed password. This allows for hash_password to be upgraded
        in the future with better algorithms, while allowing verify_password
        to be able to verify passwords hashed using old versions.

        :param password: the user supplied password encoded as bytes
        :param password_hash: a hash previously determined using hash_password()
        """

        if not isinstance(password, bytes):
            raise TypeError("expected bytes received %s" % type(password))

        if not isinstance(password_hash, str):
            raise TypeError("expected bytes received %s" % type(password))

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(password)
        key_material = digest.finalize()

        parts = password_hash.encode('utf-8').split(b':')
        kind = parts[0]
        version = parts[1]
        params = base64.b64decode(parts[2])
        data = base64.b64decode(parts[3])

        if kind != b'scrypt' or version != b"1":
            raise ValueError("invalid method")

        if version != b"1":
            raise ValueError("invalid version")

        e = None
        try:
            N, r, p, salt_length, length = struct.unpack(">HBBBB", params)
        except struct.error as ex:
            e = ValueError(str(ex))
        if e:
            raise e

        salt = data[:salt_length]
        expected = data[salt_length:]

        kdf = scrypt.Scrypt(salt, length, N, r, p, backend=default_backend())

        result = False
        try:
            kdf.verify(key_material, expected)
            result = True
        except InvalidKey as e:
            pass

        return result


def main():  # pragma: no cover

    key = b"hello world"
    t0 = time.time()
    hash = Auth.hash_password(key)
    t1 = time.time()
    print(t1 - t0)
    print(len(hash), hash)

    print(Auth.verify_password(key, hash))
    print(Auth.verify_password(b"1", hash))

if __name__ == '__main__':  # pragma: no cover
    main()
