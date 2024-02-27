[Home](../README.md)




# Network protocol

This document describes the implementation details of the UDP network protocol

The protocol is based on these documents:

* https://www.gafferongames.com/post/packet_fragmentation_and_reassembly/
* https://www.gafferongames.com/post/sending_large_blocks_of_data/
* https://pvigier.github.io/2019/09/08/beginner-guide-game-networking.html
* https://technology.riotgames.com/news/valorants-128-tick-servers

## Establishing a Connection

In order for a client to connect to the server a series of 3 special
messages are sent back and forth. After the first two messages are received
all subsequent messages are encrypted.

1. Client sends packet 'CLIENT_HELLO'

The client sends an ephemeral public key and a version identifier.

This packet is unencrypted. A simple crc32 is used to verify the integrity.

2. Server responds with packet 'SERVER_HELLO'

The server responds with an ephemeral public key unique to this client,
as well as a salt and token. The salt is used by the client to derive a shared
secret key for encryption. The token should be encrypted and sent back to
the server to validate both sides of the connection are using the correct protocol.

This packet is unencrypted. A simple crc32 is used to verify the integrity.
In addition, the datagram payload is signed using the server root key.
This will allow the client to verify that the content came from the server.

3. Client responds with 'CHALLENGE_RESP'

The client then sends the token back to the server.

This packet is encrypted. The server uses this packet to prove that both
sides were able to generate the same shared secret.

## Message Size

The maximum message size is limited by the MTU of the network.
Thats 1500 bytes for a UDP datagram, minus 28 bytes for the UDP header.
A further 20 bytes are used for the MpGameServer header.

User defined messages have an additional 2 byte overhead. When multiple messages are
encoded into a single packet the overhead increases to 5 bytes per message.
This leaves a maximum of 1450 useable bytes for a single user defined message.


todo: sequence diagram



* [SeqNum](#seqnum)
* [BitField](#bitfield)
* [PacketHeader](#packetheader)
* [Packet](#packet)
* [PendingMessage](#pendingmessage)
* [PacketIdentifier](#packetidentifier)
* [PacketType](#packettype)
* [ConnectionStatus](#connectionstatus)
* [RetryMode](#retrymode)
---
## SeqNum
A sequence number is an integer which wraps around after reaching a maximum value.

A value of zero marks an invalid or uninitialized sequnce number The first sequence number sent by the server will be 1, and after wrapping around the maximum will be set to 1 again.

Sorting is undefined over a large range




#### Class Methods:

 **maximum**`() -> int` - 

#### Methods:

 **diff**`(self, other) -> int` - returns the difference between two sequence numbers

  * **other:** 

  This implements 'traditional integer' subtraction as opposed to what __sub__ implements

  The sign of the output will be corrected if the numbers wrapped

  Example: 0xFFF0 - 0x000A = -25 0x000A - 0xFFF0 = +25

  Proof Example 1: 0xFFF0 - (0xFFF0 + 25) = x 0xFFF0 - 0xFFF0 - 25 = x - 25 = x

  Proof Example 2:

  (0xFFF0 + 25) - 0xFFF0 = x 0xFFF0 + 25 - 0xFFF0 = x + 25 = x

  

 **newer_than**`(self, other)` - Test

  * **other:** 

  * **returns:** True if this SeqNum is more recent than the given SeqNum

  

---
## BitField
The bitfield keeps track of recently received messages. It uses a one hot encoding to indicate received SeqNum using a fixed number of bits.




#### Constructor:

 **BitField**`(self, nbits=32)` - 

  * **nbits:** the number of bits to use for encoding the history of inserted messages

  


#### Methods:

 **contains**`(self, seqnum: mpgameserver.connection.SeqNum)` - test if the bitfield currently contains the Sequence Number

  * **seqnum:** The Sequence Number

  

 **insert**`(self, seqnum: mpgameserver.connection.SeqNum)` - insert a sequence number

  * **seqnum:** The Sequence Number

  raises a DuplicationError if an exception is thrown

  

---
## PacketHeader
The Packet Header structure is composed of the following:



| Num. Bytes | Field Name | Description |
| -----: | :--- | :---------- |
| 3 | magic number           | packet protocol version identifier |
| 1 | direction identifier   | identify whether the packet is to be decrypted by the client or server. Used to prevent IV reuse between client and server |
| 4 | send time              | time packet was constructed. used to generate a unique IV when combined with incrementing seq num |
| 2 | seq num                | incrementing packet counter |
| 2 | previous acked seq num | sequence number of the last received packet |
| 1 | packet type            | describbes payload content |
| 2 | length                 | number of bytes in the payload excluding any CRC or AES-GCM tag |
| 1 | count                  | number of messages in this packet |
| 4 | ack_bits               | bit field indicating what messages have been received from remote |

The first 12 bytes of the header are used as the IV when encrypting a packet. The entire header is 20 bytes. When encrypting a packet the header is included as part of the AAD, and not encrypted.




#### Constructor:

 **PacketHeader**`(self)` - 

#### Public Attributes:

**`ack`**: the SeqNum of the last packet received from remote

**`ack_bits`**: 32-bit integer bit-field indicating received packets

**`count`**: number of messages included in the packet

**`ctime`**: the current time

**`isServer`**: True when it is the server constructing the header

**`length`**: number of data bytes in packet

**`pkt_type`**: The type of this packet

**`seq`**: the SeqNum for this Packet


#### Static Methods:

 **create**`(isServer, ctime, pkt_type, seq, ack, ack_bits)` - contruct a new header

  * **isServer:** True when it is the server constructing the header

  * **ctime:** the current time

  * **pkt_type:** The type of this packet

  * **seq:** the SeqNum for this Packet

  * **ack:** the SeqNum of the last packet received from remote

  * **ack_bits:** 32-bit integer bit-field indicating received packets

  

 **from_bytes**`(isServer, datagram)` - extract the header from a datagram

  * **isServer:** True when it is the server that is extracting the header

  * **datagram:** the bytes to decode

  


#### Methods:

 **to_bytes**`(self)` - Serialize the packet header to a byte array

  

---
## Packet



#### Constructor:

 **Packet**`(self)` - 

#### Static Methods:

 **create**`(hdr: mpgameserver.connection.PacketHeader, msgs: List[mpgameserver.connection.PendingMessage])` - create a new packet given a header and a list messages

  * **hdr:** 

  * **msgs:** 

  hdr: PacketHeader msgs: list of PendingMessage

  

 **from_bytes**`(hdr, key, datagram)` - 

  * **hdr:** 

  * **key:** 

  * **datagram:** 
 **overhead**`(n)` - return the amount of overhead for n messages in a packet

  * **n:** 

  there is 2 bytes of overhead for a single message to include the message sequence number. There is 5 bytes of overhead for 2 or more messages to include the length, type, and message sequence number

  

 **setMTU**`(mtu)` - set the MTU size for the network protocol, and adjust global constants accordingly.

  * **mtu:** Maximum transmission unit.

  calling this function will change the size of packets that are constructed by the protocol.

  The default MTU is 1500 bytes. Values larger than this will result in packets that are likely to not be delivered. The MTU can be decreased if the network is dropping packets.

  The UDP header size is assumed to be 28 bytes.

  


#### Methods:

 **to_bytes**`(self, key)` - 

  * **key:** 
 **total_size**`(self, key)` - return the size of the encoded packet

  * **key:** 

  

---
## PendingMessage



#### Constructor:

 **PendingMessage**`(self, seq, type, payload, callback, retry)` - 

  * **seq:** 

  * **type:** 

  * **payload:** 

  * **callback:** 

  * **retry:** 
---
##  PacketIdentifier
The packet magic number. Used to cheaply identify a packet as originating from a client or server implementing the MpGameServer protocol



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| TO_CLIENT | b'FSOC' | Indicates a packet being sent to a client |
| TO_SERVER | b'FSOS' | Indicates a packet being sent to the server |
---
##  PacketType
The CLIENT_HELLO, SERVER_HELLO, CHALLENGE_RESP types implement a three way handshake that agree on an encryption key and verify both sides are implementing the same protocol.



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| UNKNOWN | 0 | not used |
| CLIENT_HELLO | 1 | sent by the client to initiate a connection |
| SERVER_HELLO | 2 | server response to the hello |
| CHALLENGE_RESP | 3 | client response to finialize the connection |
| KEEP_ALIVE | 4 | for packets automatically generated by a timeout |
| DISCONNECT | 5 | client or server packet indicating graceful disconnect |
| APP | 6 | user defined packet |
| APP_FRAGMENT | 7 | user defined packet was split into fragments |
---
##  ConnectionStatus
The connection status



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| CONNECTING | 1 | the client is attempting to connect, keys are not set |
| CONNECTED | 2 | the client is connected, keys are set |
| DISCONNECTING | 3 | the client is closing the connection gracefully |
| DISCONNECTED | 4 | the client is not connected |
| DROPPED | 5 | the client lost communication with the server |
---
##  RetryMode
The RetryMode is a per-message setting which controls how the message is delivered.

When using one of the retry modes, it is possible for the same message to be included in multiple datagrams. The protocol automatically detects and drops duplicate messages.



| Attribute | Enum Value | Description |
| :-------- | ---------: | :---------- |
| RETRY_ON_TIMEOUT | -1 | Send the message. If a timeout occurs automatically resend the message. The message will be sent in this fashion until received or the connection is closed. |
| NONE | 0 | Send the message, with no attempt at guaranteeing delivery or retrying. |
| BEST_EFFORT | 1 | Send the message. Then resend on the keep alive interval until the message is acked or the timeout duration is reached. Note: It is possible for the message to be received, but the timeout may still trigger. |
