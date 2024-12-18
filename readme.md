# nixa

`nixa` is an ansible-like configuration management tool for deployment and day-2 operations of NixOS servers.

This project is under construction.

Forked from https://github.com/nihr43/nk3

## usage

Given an inventory of ssh-reachable hosts:

```
---

routers:
  hosts:
    - 10.38.154.98
    - 10.38.154.87
    - 10.38.154.160
  templates:
    - lxc.nix
  nix-channel: 24.11
```

`routers` is a user-specified group name.  `hosts`, `templates`, and `nix-channel` are required for each group.

Running `main.py` loops through the hosts, lands the template, and either 'switchs' or reboots.  Concatination of multiple templates, like ansible roles, is TODO.

```
nixa > nix-shell . --run 'python3 main.py --nixos-action switch'
d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19 is reachable
0a6dd2c3-bc17-59c5-859b-b9c9921b7961 is reachable
86da48cb-c4ad-548b-9859-dfd7a3ee1d87 is reachable
applying template lxc.nix to ['d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19', '0a6dd2c3-bc17-59c5-859b-b9c9921b7961', '86da48cb-c4ad-548b-9859-dfd7a3ee1d87']
d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19 modified:
--- 

+++ 

@@ -8,6 +8,7 @@

   networking.hostName = "d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19";
 
   environment.systemPackages = with pkgs; [
+    htop
     busybox
   ];
 
Rebuilding NixOS on d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19
0a6dd2c3-bc17-59c5-859b-b9c9921b7961 modified:
--- 

+++ 

@@ -8,6 +8,7 @@

   networking.hostName = "0a6dd2c3-bc17-59c5-859b-b9c9921b7961";
 
   environment.systemPackages = with pkgs; [
+    htop
     busybox
   ];
 
Rebuilding NixOS on 0a6dd2c3-bc17-59c5-859b-b9c9921b7961
86da48cb-c4ad-548b-9859-dfd7a3ee1d87 modified:
--- 

+++ 

@@ -8,6 +8,7 @@

   networking.hostName = "86da48cb-c4ad-548b-9859-dfd7a3ee1d87";
 
   environment.systemPackages = with pkgs; [
+    htop
     busybox
   ];
 
Rebuilding NixOS on 86da48cb-c4ad-548b-9859-dfd7a3ee1d87
```

If an error is found in the configuration, the changes will be reverted and the run aborted:

```
nix-shell . --run 'python3 main.py'
d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19 is reachable
0a6dd2c3-bc17-59c5-859b-b9c9921b7961 is reachable
86da48cb-c4ad-548b-9859-dfd7a3ee1d87 is reachable
applying template lxc.nix to routers: ['d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19', '0a6dd2c3-bc17-59c5-859b-b9c9921b7961', '86da48cb-c4ad-548b-9859-dfd7a3ee1d87']
d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19 modified:
--- 

+++ 

@@ -10,6 +10,8 @@

   environment.systemPackages = with pkgs; [
     busybox
   ];
+
+  networking.nomeservers = ["1.1.1.1"];
 
   networking = {
     dhcpcd.enable = false;
Rebuilding NixOS on d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19
Encountered a bad command exit code!

Command: 'nixos-rebuild boot'

Exit code: 1

Stdout:



Stderr:

             |                  ^
          323|         _module = checked (config._module);

       (stack trace truncated; use '--show-trace' to show the full trace)

       error: The option `networking.nomeservers' does not exist. Definition values:
       - In `/etc/nixos/configuration.nix':
           [
             "1.1.1.1"
           ]


`nixos-rebuild` failed on d14d90c2-4e69-5cb0-ac9d-e1ca0ce71c19.  Changes reverted.
error: Recipe `apply` failed on line 2 with exit code 1
```
