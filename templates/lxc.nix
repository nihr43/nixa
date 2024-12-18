{ modulesPath, pkgs, ... }:

{
  imports = [
    "${modulesPath}/virtualisation/lxc-container.nix"
  ];

  networking.hostName = "{{attrs.hostname}}";

  environment.systemPackages = with pkgs; [
    busybox
    htop
  ];

  boot.tmp.cleanOnBoot = true;
  nix.optimise.automatic = true;
  nix.gc = {
    automatic = true;
    options = "--delete-older-than 7d";
  };

  services.openssh = {
    enable = true;
    startWhenNeeded = false;
    settings = {
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
      PermitRootLogin = "yes";
    };
  };

  users.users.root.openssh.authorizedKeys.keys = [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKL+1xp+nQIbu02D1NmU+4RTPGblUML21TSzF/Pxg5GM"
  ];

  system.stateVersion = "24.11";
}
