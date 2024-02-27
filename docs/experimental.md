[Home](../README.md)
* [TaskPool](#taskpool)
* [Auth](#auth)

# Experimental Modules
The classes documented here are experimental and may have breaking API changes in the future.


---
## TaskPool
A Task Pool provides a thread safe mechanism for running long lived operations inside a separate process to avoid blocking the main game loop.

The event handler can submit a task at any time. When the task completes the task pool update will process the callbacks.

The event handler events Update and Shutdown should call the appropriate task pool method.




#### Constructor:

 **TaskPool**`(self, processes=1, maxtasksperchild=None)` - 

  * **processes:** 

  * **maxtasksperchild:** 

#### Methods:

 **shutdown**`(self)` - cancel running tasks and stop the task pool
 **submit**`(self, fn, args=(), kwargs={}, callback=None, error_callback=None)` - submit a task to be run in a background process

  * **fn:** a function to be run in a background process

  * **args:** the positional arguments to fn, if any

  * **kwargs:** the keyword arguments to fn, if any

  * **callback:** a callback function which accepts a single argument, the return value from fn. The callback is called if the function exits without an exception.

  * **error_callback:** a callback function which accepts a single argument, the exception value from fn. The callback is called if the function exits because of an unhandled exception.

  

 **update**`(self)` - check for completed tasks and process the callbacks.

  

---
## Auth
Password hashing and verification

Note: Both hashing and verifying passwords are expensive operations, taking around .1 to .2 seconds. The server event handler should use a TaskPool to run the authentication in a background process and handle the result asynchronously.

Note: this does not encrypt the password. Theoretically, it is not possible to reverse the hash to recover the given password.




#### Public Attributes:

**`DIGEST_LENGTH`**: The length of the generated hash. 24 bytes.

**`SALT_LENGTH`**: The length of the salt generated when hashing. 16 bytes.


#### Static Methods:

 **hash_password**`(password: bytes) -> str` - hash a password

  * **password:** the user supplied password encoded as bytes

  * **returns:** the hashed password

  The output string contains the parameters used to define the hash, as well as the randomly generated salt used.

  Implementation notes: This method pre-hashes the password using sha-256. A salt is generated and then it then hashes the output using scrypt with parameters N=16384, r=16, p=1.

  

 **verify_password**`(password: bytes, password_hash: str) -> bool` - verify a given password matches the given password hash

  * **password:** the user supplied password encoded as bytes

  * **password_hash:** a hash previously determined using hash_password()

  raises TypeError, ValueError if the input is not well formed

  returns True if the password matches the hash. otherwise False

  The output of hash_password contains the parameters and salt as well as the hashed password. This allows for hash_password to be upgraded in the future with better algorithms, while allowing verify_password to be able to verify passwords hashed using old versions.

  

