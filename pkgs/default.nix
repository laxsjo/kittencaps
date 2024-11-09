{
  self,
  inputs,
}:

final: prev: import ./pkgs.nix { inherit self inputs; pkgs = final; }
