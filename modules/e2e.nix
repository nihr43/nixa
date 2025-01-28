{ modulesPath, pkgs, ... }: {
  imports = [
    "${modulesPath}/virtualisation/incus-virtual-machine.nix"
  ];

  system.stateVersion = "{{hostvars["stateversion"]}}";
  networking.hostName = "{{hostvars["hostname"]}}";

  environment.systemPackages = with pkgs; [
    busybox
    htop
  ];

  users.users.root.openssh.authorizedKeys.keys = [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKL+1xp+nQIbu02D1NmU+4RTPGblUML21TSzF/Pxg5GM"
  ];

  services.openssh = {
    enable = true;
    startWhenNeeded = false;
    settings.KbdInteractiveAuthentication = false;
    settings.PasswordAuthentication = false;
    settings.PermitRootLogin = "yes";
  };
}
