[Home](../README.md)



# Client



* [UdpClient](#udpclient)
* [ConnectionStats](#connectionstats)
* [ConnectionStatus](#connectionstatus)
* [RetryMode](#retrymode)
---
## UdpClient
This class manages UDP socket connection to the server.

The Client is designed to be non-blocking so that it can be run inside the main loop of the game. The update() function should be called once per frame to perform the actual send and receive of messages. Messages can be queued at any time using send()

The server public key is a Elliptic Curve public key that should be generated once from the server private key and stored and distributted with the client. The key is used to authenticate that the server this client is connecting to is in fact a genuine server.




#### Constructor:

* :small_blue_diamond: **`UdpClient`**`(self, server_public_key=None)` - 

  * **:arrow_forward: `server_public_key:`** the public key used to identify the server

  


#### Methods:

* :small_blue_diamond: **`connect`**`(self, addr, callback: Callable[[bool], NoneType] = None)` - connect to a udp socket server

  * **:arrow_forward: `addr:`** a 2-tuple (host, port)

  * **:arrow_forward: `callback:`** a callable object to handle connection success or timeout callback signature: `fn(connected: bool)`

  

* :small_blue_diamond: **`connected`**`(self) -> bool` - 

  * **:leftwards_arrow_with_hook: `returns:`** True if the client is connected to the server

  

* :small_blue_diamond: **`disconnect`**`(self)` - disconnect from the server.

  This method only sets an internal flag to disconnect. use waitForDisconnect() to send a disconnect to the server and wait for the subsequent ack.

  

* :small_blue_diamond: **`forceDisconnect`**`(self)` - 
* :small_blue_diamond: **`getMessage`**`(self)` - get a single message received from the server

  * **:leftwards_arrow_with_hook: `returns:`** a tuple (seqnum, msg)

  raises IndexError if the incoming message queue is empty

  This is a destructive call. It removes one message from the queue

  

* :small_blue_diamond: **`getMessages`**`(self)` - This is a destructive call. It removes all messages from the internal queue

  * **:leftwards_arrow_with_hook: `returns:`** The list of unprocessed messages from the server, or an empty list

  

* :small_blue_diamond: **`hasMessages`**`(self)` - 

  * **:leftwards_arrow_with_hook: `returns:`** True if there are unprocessed messages from the server

  

* :small_blue_diamond: **`latency`**`(self)` - latency is the weighted average time it takes from sending a packet until it is acked.

  * **:leftwards_arrow_with_hook: `returns:`** The connection latency

  

* :small_blue_diamond: **`send`**`(self, msg: bytes, retry: int = -1, callback: Callable[[bool], NoneType] = None)` - send a message to the server

  * **:arrow_forward: `msg:`** the bytes to send

  * **:arrow_forward: `retry:`** the RetryMode, default to RetryMode.NONE

  * **:arrow_forward: `callback:`** a function which is called when the message has been acked or after a timeout. The function should accept a single boolean which is true when the message is acked and false otherwise. If retry is negative then the callback will be called when the message is finally acked.

  The message is not sent immediatly, Instead on the next call to update() a datagram will be sent.

  The message will be fragmented if the length is greater than Packet.MAX_PAYLOD_SIZE

  

* :small_blue_diamond: **`send_guaranteed`**`(self, payload: bytes, callback: Callable[[bool], NoneType] = None)` - send the message and guarantee delivery by using RetryMode.RETRY_ON_TIMEOUT

  * **:arrow_forward: `payload:`** 

  * **:arrow_forward: `callback:`** 

  

* :small_blue_diamond: **`setConnectionTimeout`**`(self, timeout)` - configure the timeout for waiting for the response to the connection request.

  * **:arrow_forward: `timeout:`** the timeout in seconds. The default is 5 seconds.

  

* :small_blue_diamond: **`setKeepAliveInterval`**`(self, interval)` - configure the timeout for sending keep alive datagrams to clients.

  * **:arrow_forward: `interval:`** 

  

* :small_blue_diamond: **`setMessageTimeout`**`(self, timeout)` - configure the timeout for waiting for the ack for a datagram

  * **:arrow_forward: `timeout:`** the timeout in seconds. The default is 1 second.

  

* :small_blue_diamond: **`stats`**`(self) -> mpgameserver.connection.ConnectionStats` - 
* :small_blue_diamond: **`status`**`(self) -> mpgameserver.connection.ConnectionStatus` - 

  * **:leftwards_arrow_with_hook: `returns:`** the ConnectionStatus

  

* :small_blue_diamond: **`token`**`(self)` - get the client token. This is a unique id generated when the client connects used internally to represent the client.

  * **:leftwards_arrow_with_hook: `returns:`** the unique id for this client

  

* :small_blue_diamond: **`update`**`(self)` - send and receive messages

  On every frame one datagram is sent to the server if there are pending messages to be sent. Each datagram will contain as many messages that can possibly fit into the packet size. The packet size is limited by the MTU size of the network, which is typically 1500 bytes. In practice the maximum packet size is 1472 bytes.

  This function should be called once per game frame. This function is not thread safe, and should be called from the same thread that is also calling send()

  

* :small_blue_diamond: **`waitForDisconnect`**`(self)` - block the current thread until the server has responded that it received the disconnect event.

  blocks up to 1 second before giving up

  

---
## ConnectionStats
Structure containing all of the connection statistics.

The attributes for packets sent/recv, bytes sent/recv and latency are sequence types where each bin is the statistics for a particular second. The list is treated as a FIFO queue, meaning lower indexes are older samples. The last index is the most recent data.




#### Public Attributes:

**`acked`**: the lifetime count of outgoing packets acked

**`assembled`**: the lifetime count of outgoing packets created

**`bytes_recv`**: a rolling list of integers. total bytes received.

**`bytes_sent`**: a rolling list of integers. total bytes sent.

**`dropped`**: the lifetime count of received packets dropped

**`latency`**: a rolling list of integers. mean latency

**`pkts_recv`**: a rolling list of integers. packets received.

**`pkts_sent`**: a rolling list of integers. packets sent.

**`received`**: the lifetime count of received packets

**`sent`**: the lifetime count of outgoing packets sent

**`timeouts`**: the lifetime count of outgoing packets that timed out

---
## :large_orange_diamond: ConnectionStatus
The connection status



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| CONNECTING | 1 | the client is attempting to connect, keys are not set |
| CONNECTED | 2 | the client is connected, keys are set |
| DISCONNECTING | 3 | the client is closing the connection gracefully |
| DISCONNECTED | 4 | the client is not connected |
| DROPPED | 5 | the client lost communication with the server |
---
## :large_orange_diamond: RetryMode
The RetryMode is a per-message setting which controls how the message is delivered.

When using one of the retry modes, it is possible for the same message to be included in multiple datagrams. The protocol automatically detects and drops duplicate messages.



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| RETRY_ON_TIMEOUT | -1 | Send the message. If a timeout occurs automatically resend the message. The message will be sent in this fashion until received or the connection is closed. |
| NONE | 0 | Send the message, with no attempt at guaranteeing delivery or retrying. |
| BEST_EFFORT | 1 | Send the message. Then resend on the keep alive interval until the message is acked or the timeout duration is reached. Note: It is possible for the message to be received, but the timeout may still trigger. |
