{
  self,
  inputs,
  pkgs,
}:

{
  open-gorton = pkgs.callPackage ./open-gorton { inherit self inputs; };
  icon-template-svg = pkgs.callPackage ./icon-template-svg { inherit self inputs; };
}
