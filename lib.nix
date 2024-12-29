{
  stdenvNoCC,
  woff2,
  poetry2nix
}:

{
  mkFont = {
    name,
    src,
  }: stdenvNoCC.mkDerivation {
    inherit name src;
    
    phases = [ "unpackPhase" "buildPhase" "installPhase" ];
    
    buildPhase = ''
      find . -name '*.woff'  -exec woff2_decompress {} \;
      find . -name '*.woff2' -exec woff2_decompress {} \;
    '';
    
    installPhase = ''
      runHook preInstall

      find . -name '*.otf'    -exec install -Dt $out/share/fonts/opentype {} \;
      find . -name '*.ttf'    -exec install -Dt $out/share/fonts/truetype {} \;
      find . -name '*.bdf'    -exec install -Dt $out/share/fonts/bdf      {} \;
      find . -name '*.pcf.gz' -exec install -Dt $out/share/fonts/pcf      {} \;
      find . -name '*.psf.gz' -exec install -Dt $out/share/consolefonts   {} \;

      runHook postInstall
    '';
    
    nativeBuildInputs = [
      woff2
    ];
  };
  
  mkPoetry2nixOverrides = requirements:
    poetry2nix.defaultPoetryOverrides.extend (self: super:
      builtins.mapAttrs (package: build-requirements:
        (builtins.getAttr package super).overridePythonAttrs (old: {
          buildInputs = (old.buildInputs or [ ])
            ++ (builtins.map
              (pkg: if builtins.isString pkg then builtins.getAttr pkg super else pkg)
              build-requirements
            );
        })
      ) requirements
    );
}
