{
  self,
  inputs,
  pkgs,
}:

{
  open-gorton = pkgs.callPackage ./open-gorton { inherit self inputs; };
}
