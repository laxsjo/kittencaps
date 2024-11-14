{
  self,
  inputs,
  
  open-gorton,
  
  system,
  fontconfig,
  stdenvNoCC
}:

let
  scripts = self.packages.${system}.scripts;
in stdenvNoCC.mkDerivation {
  name = "embedded-font-svg";
  src = inputs.nix-filter {
    root = self;
    include = [
      "src"
    ];
  };
  fontsSrc = open-gorton;
  
  buildPhase = ''
    args=()
    for file in $(find $fontsSrc -regextype awk -regex '.*(ttf|otf|woff|woff2)'); do
      args+=("--font" "$file")
    done
    generate_icon "''${args[@]}" > $out
  '';
  
  
  nativeBuildInputs = [
    scripts
    fontconfig
    open-gorton
  ];
}
