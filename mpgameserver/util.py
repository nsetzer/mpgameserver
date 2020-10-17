

import socket

def is_valid_ipv6_address(hostname):
    try:
        socket.inet_pton(socket.AF_INET6, hostname)
    except socket.error:
        return False
    return True