# Network play and Messenger ID

## Host a room

```
host 45678
```

The host starts an asyncio server on `0.0.0.0:45678`. The player gets a stable
`Messenger ID` such as `skay_user_9fk21ab03c`. It is stored in
`config/identity.json` and does not change after a restart.

## Join by IP

```
join 192.168.1.42 45678
```

The client connects to a real LAN IP once. After the handshake, only Messenger
IDs are shown in the interface.

## Encryption

X25519 (ephemeral) to HKDF-SHA256 to AESGCM. Each direction has its own nonce
counter. The host relays messages to the recipient ID.

## Messenger

```
id                       # your ID
peers                    # list of participants
msg skay_user_xxx hello  # private message
leave                    # leave the room
```

All commands also accept a leading `/`, for example `/help /scan`.

Attacks only target virtual Server Empire IPs (`10.60.x.y`) and never leave the
real network.
