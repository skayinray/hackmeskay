# Server empire

The empire is a tree of virtual nodes stored in `saves/empire.sqlite3`.

```
empire build              # gateway -> vpn/c2 -> mainframe
empire status             # list nodes
/scan 10.60.4.12          # simulated service versions and vulnerabilities
/trace 10.60.4.12         # unwind the VPN/C2 chain
breach 10.60.4.12 --captcha
empire rootkit <node_id>  # feed false logs to the opponent
```

## Node types

- **Gateway** is the only type visible from outside and has a firewall and
  captcha.
- **VPN/C2** nodes are hidden and lengthen the route chain.
- **Mainframe** stores crypto and files. Its IP is visible only after `/trace`.

A rootkit on a proxy changes `/scan` output and adds a false trail to `/trace`,
so the opponent wastes turns on an empty node.

`/scan`, `/trace` and `breach` work with a local SQLite model. No real network
requests are sent to the given IP addresses.
