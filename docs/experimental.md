[Home](../README.md)
* [TaskPool](#taskpool)
* [Captcha](#captcha)
* [Auth](#auth)

# Experimental Modules
The classes documented here are experimental and may have breaking API changes in the future.


---
## TaskPool
A Task Pool provides a thread safe mechanism for running long lived operations inside a separate process to avoid blocking the main game loop.

The event handler can submit a task at any time. When the task completes the task pool update will process the callbacks.

The event handler events Update and Shutdown should call the appropriate task pool method.




#### Constructor:

* :small_blue_diamond: **`TaskPool`**`(self, processes=1, maxtasksperchild=None)` - 

  * **:arrow_forward: `processes:`** 

  * **:arrow_forward: `maxtasksperchild:`** 

#### Methods:

* :small_blue_diamond: **`shutdown`**`(self)` - cancel running tasks and stop the task pool
* :small_blue_diamond: **`submit`**`(self, fn, args=(), kwargs={}, callback=None, error_callback=None)` - submit a task to be run in a background process

  * **:arrow_forward: `fn:`** a function to be run in a background process

  * **:arrow_forward: `args:`** the positional arguments to fn, if any

  * **:arrow_forward: `kwargs:`** the keyword arguments to fn, if any

  * **:arrow_forward: `callback:`** a callback function which accepts a single argument, the return value from fn. The callback is called if the function exits without an exception.

  * **:arrow_forward: `error_callback:`** a callback function which accepts a single argument, the exception value from fn. The callback is called if the function exits because of an unhandled exception.

  

* :small_blue_diamond: **`update`**`(self)` - check for completed tasks and process the callbacks.

  

---
## Captcha
Note: the default settings for both create() and getBytes() are tuned to produce an image which will fit inside of a single UDP packet, and allow for some overhead




#### Constructor:

* :small_blue_diamond: **`Captcha`**`(self, code, image)` - 

  * **:arrow_forward: `code:`** 

  * **:arrow_forward: `image:`** 

#### Public Attributes:

**`code`**: the string contained in the image

**`image`**: the image challenge


#### Static Methods:

* :small_blue_diamond: **`create`**`(font_file=None, code_length=5, bgc=(255, 255, 255), size=(100, 25), rotate=60)` - 

  * **:arrow_forward: `font_file:`** 

  * **:arrow_forward: `code_length:`** 

  * **:arrow_forward: `bgc:`** the background color of the image

  * **:arrow_forward: `size:`** a 2-tuple (width, height) in pixels

  * **:arrow_forward: `rotate:`** maximum degrees to rotate a single character. a character will be rotated by a random value +/- rotate/2

  


#### Methods:

* :small_blue_diamond: **`getBytes`**`(self, quality=25)` - 

  * **:arrow_forward: `quality:`** 0 to 100, default 25. use 75 for 'best quality' see the PIL documentation for more information

  

* :small_blue_diamond: **`validate`**`(self, text)` - compare a given string to the code

  * **:arrow_forward: `text:`** 

  Performs a constant time comparison that is case insensitive.

  returns true when the given text matches the code

  

---
## Auth
Password hashing and verification

Note: Both hashing and verifying passwords are expensive operations, taking around .1 to .2 seconds. The server event handler should use a TaskPool to run the authentication in a background process and handle the result asynchronously.

Note: this does not encrypt the password. Theoretically, it is not possible to reverse the hash to recover the given password.




#### Public Attributes:

**`DIGEST_LENGTH`**: The length of the generated hash. 24 bytes.

**`SALT_LENGTH`**: The length of the salt generated when hashing. 16 bytes.


#### Static Methods:

* :small_blue_diamond: **`hash_password`**`(password: bytes) -> str` - hash a password

  * **:arrow_forward: `password:`** the user supplied password encoded as bytes

  * **:leftwards_arrow_with_hook: `returns:`** the hashed password

  The output string contains the parameters used to define the hash, as well as the randomly generated salt used.

  Implementation notes: This method pre-hashes the password using sha-256. A salt is generated and then it then hashes the output using scrypt with parameters N=16384, r=16, p=1.

  

* :small_blue_diamond: **`verify_password`**`(password: bytes, password_hash: str) -> bool` - verify a given password matches the given password hash

  * **:arrow_forward: `password:`** the user supplied password encoded as bytes

  * **:arrow_forward: `password_hash:`** a hash previously determined using hash_password()

  raises TypeError, ValueError if the input is not well formed

  returns True if the password matches the hash. otherwise False

  The output of hash_password contains the parameters and salt as well as the hashed password. This allows for hash_password to be upgraded in the future with better algorithms, while allowing verify_password to be able to verify passwords hashed using old versions.

  

