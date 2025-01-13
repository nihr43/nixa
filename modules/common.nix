{ pkgs, ... }: {
  boot.loader.grub.devices = ["/dev/sda"];
  boot.tmp.cleanOnBoot = true;
  nix.optimise.automatic = true;
  nix.gc.automatic = true;
  system.stateVersion = "{{hostvars["stateversion"]}}";

  services.openssh = {
    enable = true;
    settings.PasswordAuthentication = false;
    settings.KbdInteractiveAuthentication = false;
    settings.PermitRootLogin = "yes";
  };

  users.users.root.openssh.authorizedKeys.keys = [
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINCh/Za19ZkYLdi3JKcJVFEVy+0+fyqetTi1Xtfn/xx+"
  ];

  environment.systemPackages = with pkgs; [
    htop
  ];
}
