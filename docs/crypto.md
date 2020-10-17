[Home](../README.md)




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

* [EllipticCurvePrivateKey](#ellipticcurveprivatekey)
* [EllipticCurvePublicKey](#ellipticcurvepublickey)
---
## :large_blue_diamond: EllipticCurvePrivateKey
A Elliptic Curve Private key used for key exchange and signing

This class implements methods for performing basic Elliptic Curve operations, such as converting between common file formats and signing data.




#### Constructor:

* :small_blue_diamond: **`EllipticCurvePrivateKey`**`(self, key=None)` - 

  * **:arrow_forward: `key:`** 

#### Static Methods:

* :small_blue_diamond: **`fromBytes`**`(der: bytes)` - 

  * **:arrow_forward: `der:`** 
* :small_blue_diamond: **`fromPEM`**`(pem: str)` - 

  * **:arrow_forward: `pem:`** 
* :small_blue_diamond: **`new`**`()` - 
* :small_blue_diamond: **`unsafeTestKey`**`()` - a default key used for testing a client and server.

  NOT FOR PRODUCTION USE

  


#### Methods:

* :small_blue_diamond: **`getBytes`**`(self)` - 
* :small_blue_diamond: **`getPrivateKeyPEM`**`(self)` - 
* :small_blue_diamond: **`getPublicKey`**`(self)` - 
* :small_blue_diamond: **`savePEM`**`(path)` - 

  * **:arrow_forward: `path:`** 
* :small_blue_diamond: **`sign`**`(self, data)` - returns a signature for the supplied data

  * **:arrow_forward: `data:`** 

  

---
## :large_blue_diamond: EllipticCurvePublicKey
A Elliptic Curve Private key used for key exchange and signing

This class implements methods for performing basic Elliptic Curve operations, such as converting between common file formats and verifying signed data.




#### Constructor:

* :small_blue_diamond: **`EllipticCurvePublicKey`**`(self, key)` - 

  * **:arrow_forward: `key:`** 

#### Public Attributes:

**`InvalidSignature`**: exception type raised by verify when signature is invalid


#### Static Methods:

* :small_blue_diamond: **`fromBytes`**`(der: bytes)` - 

  * **:arrow_forward: `der:`** 
* :small_blue_diamond: **`fromPEM`**`(pem: str)` - 

  * **:arrow_forward: `pem:`** 
* :small_blue_diamond: **`unsafeTestKey`**`()` - a default key used for testing a client and server.

  NOT FOR PRODUCTION USE

  


#### Methods:

* :small_blue_diamond: **`getBytes`**`(self)` - 
* :small_blue_diamond: **`getPublicKeyPEM`**`(self)` - 
* :small_blue_diamond: **`savePEM`**`(path)` - 

  * **:arrow_forward: `path:`** 
* :small_blue_diamond: **`verify`**`(self, signature, data)` - validate that the supplied data matches a signature

  * **:arrow_forward: `signature:`** 

  * **:arrow_forward: `data:`** 

  raises an InvalidSignature exception on error

  

