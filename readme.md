# nixa

`nixa` is an ansible-like configuration management tool for deployment and day-2 operations of NixOS servers.

Forked from https://github.com/nihr43/nk3

## usage

Given an inventory of ssh-reachable hosts:

```
---
routers:
  hosts:
    10.0.0.0:
      hostname: spine-green-476d
      stateversion: 24.11
      loopback: 10.0.0.0
      as_number: 64512
      bgp_interfaces:
        - enp3s0
        - enp4s0
        - enp0s20f0
        - enp0s20f1
        - enp0s20f2
        - enp0s20f3
    10.0.0.1:
      hostname: spine-blue-db5d
      stateversion: 24.11
      loopback: 10.0.0.1
      as_number: 64512
      bgp_interfaces:
        - enp3s0
        - enp4s0
        - enp0s20f0
        - enp0s20f1
        - enp0s20f2
        - enp0s20f3
  modules:
    - bgp.nix
    - serial.nix
    - common.nix
  nix-channel: nixos-24.11
```

Modules `bgp.nix` `serial.nix` and `common.nix` are sourced from `modules/`.

Variables such as `bgp_interfaces` are available in dict `hostvars`, using jinja syntax:

```
{% for i in hostvars["bgp_interfaces"] %}
        neighbor {{i}} interface remote-as external
{% endfor %}
```

Ultimately, these modules are templated, copied to hosts, and imported in `configuration.nix`:

```
{
  imports = [
    ./hardware-configuration.nix
    ./bgp.nix
    ./serial.nix
    ./common.nix
  ];
}
```

`hardware-configuration.nix` is untouched.

To apply configuration across a specific group, two nodes at a time:

```
nix-shell --run 'python3 nixa --limit datto --parallel 2'
```

```
10.0.0.2 is reachable
10.0.0.3 is reachable
applying template bgp.nix to datto: ['10.0.0.2', '10.0.0.3']
10.0.0.2:
10.0.0.3:
--- 

+++ 

@@ -36,6 +36,7 @@

 
       router bgp 64512
         bgp router-id 10.0.0.2
+        bgp fast-convergence
         bgp bestpath as-path multipath-relax
 
         neighbor enp3s0 interface remote-as external
--- 

+++ 

@@ -36,6 +36,7 @@

 
       router bgp 64512
         bgp router-id 10.0.0.3
+        bgp fast-convergence
         bgp bestpath as-path multipath-relax
 
         neighbor enp3s0 interface remote-as external
rebuilding NixOS on 10.0.0.2
rebuilding NixOS on 10.0.0.3
```

## OS upgrades

`nixa` provides a mechanism for nixos-native OS upgrades:

```
nixa > nix-shell . --run 'python3 main.py --upgrade'
f676954e-858b-5ebc-91b7-70aeda560465 is reachable
0a6dd2c3-bc17-59c5-859b-b9c9921b7961 is reachable
86da48cb-c4ad-548b-9859-dfd7a3ee1d87 is reachable
upgrading f676954e-858b-5ebc-91b7-70aeda560465
enforcing nixos channel nixos-24.11
45 paths fetched
200 derivations built
upgrading 0a6dd2c3-bc17-59c5-859b-b9c9921b7961
enforcing nixos channel nixos-24.11
45 paths fetched
199 derivations built
upgrading 86da48cb-c4ad-548b-9859-dfd7a3ee1d87
enforcing nixos channel nixos-24.11
45 paths fetched
199 derivations built
```

Whatever channel `nix-channel:` is set to in the inventory is enforced.  For regular 'daily' upgrades, just run `--upgrade`.  For Release upgrades, go increment the channel in the inventory, then run `--upgrade`.
