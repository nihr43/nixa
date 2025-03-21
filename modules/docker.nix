{
  virtualisation.docker.enable = true;
  virtualisation.oci-containers = {
    backend = "docker";
    containers = {
      nginx = {
        image = "nginx:latest";
        ports = [ "80:80" ];
        autoStart = true;
      };
    };
  };
}
