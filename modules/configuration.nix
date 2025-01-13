{
  imports = [
    ./hardware-configuration.nix
{% for m in modules %}
    ./{{m}}
{% endfor %}
  ];
}
