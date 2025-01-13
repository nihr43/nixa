{
  networking = {
    hostName = "{{hostvars["hostname"]}}";
    nameservers = [ "1.1.1.1" ];
    firewall.enable = false;
    useDHCP = false;
    interfaces.lo.ipv4.addresses = [{
      address = "{{hostvars["loopback"]}}";
      prefixLength = 32;
    }];
{% for i in hostvars["bgp_interfaces"] %}
    interfaces.{{i}}.useDHCP = false;
{% endfor %}
  };

  boot.kernel.sysctl = {
    "net.ipv4.conf.all.forwarding" = 1;
    "net.ipv4.fib_multipath_use_neigh" = 1;
    "net.ipv4.fib_multipath_hash_policy" = 1;
  };

  services.frr = {
    bgpd.enable = true;
    config = ''
      frr defaults datacenter

      router bgp {{hostvars["as_number"]}}
        bgp router-id {{hostvars["loopback"]}}
        bgp fast-convergence
        bgp bestpath as-path multipath-relax
{% for i in hostvars["bgp_interfaces"] %}
        neighbor {{i}} interface remote-as external
{% endfor %}
        address-family ipv4 unicast
          redistribute connected
{% for i in hostvars["bgp_interfaces"] %}
          neighbor {{i}} route-map default in
{% endfor %}

      ip prefix-list p1 permit 10.0.0.0/16 ge 32
      ip prefix-list p1 permit 172.30.0.0/16 ge 24
      ip prefix-list p1 permit 0.0.0.0/0

      route-map default permit 10
        match ip address prefix-list p1
    '';
  };
}
