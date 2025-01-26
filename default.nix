{ nixpkgs ? import <nixpkgs> {  } }:

let
  pkgs = with nixpkgs.python312Packages; [
    pycryptodome
    jinja2
    fabric
    pyyaml
    termcolor
    pip
  ];

in
  nixpkgs.stdenv.mkDerivation {
    name = "env";
    buildInputs = pkgs;
  }
