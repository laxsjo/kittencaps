# Loosly based on https://gist.github.com/cdepillabout/f7dbe65b73e1b5e70b7baa473dafddb3

{
  description = "Flake for generating the open source keycap set Kittencaps";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    nix-filter.url = "github:numtide/nix-filter";
    poetry2nix.url = "github:nix-community/poetry2nix";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix, ... }@inputs:
    let
      name = "kittencaps";
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin" ];
    in
    (flake-utils.lib.eachSystem supportedSystems (system: let
      lib = self.lib.${system};
    
      # nixpkgs without our overlay (to prevent cyclic dependencies)
      pkgsNoOverlay = import nixpkgs {
        inherit system;
        overlays = [ poetry2nix.overlays.default ];
      };
      pkgs = import nixpkgs {
        inherit system;
        overlays = [
          poetry2nix.overlays.default
          self.overlays.default
        ];
      };
      pypkgsBuildRequirements = {};
      pythonEnv = (pkgs.poetry2nix.mkPoetryEnv {
        overrides = lib.mkPoetry2nixOverrides pypkgsBuildRequirements;
        projectDir = self;
        python = pkgs.python312;
      });
      pythonApp = pkgs.poetry2nix.mkPoetryApplication { projectDir = ./.; };
    in {
      lib = pkgsNoOverlay.callPackage ./lib.nix {};
      inherit pythonEnv;
      packages = {
        inherit (pkgs) open-gorton icon-template-svg;
        scripts = pythonApp;
      };
      apps = {
        generate_embedded_font_svg = {
          type = "app";
          # replace <script> with the name in the [tool.poetry.scripts] section of your pyproject.toml
          program = "${pythonApp}/bin/generate_embedded_font_svg";
        };
        package_keycaps = {
          type = "app";
          # replace <script> with the name in the [tool.poetry.scripts] section of your pyproject.toml
          program = "${pythonApp}/bin/package_keycaps";
        };
      };
      devShells.default = pkgs.mkShellNoCC {
        packages = [
          pythonEnv
          pkgs.poetry
          pkgs.just
          pkgs.open-gorton
        ];
      };
      
      # Dev shell with only poetry. Use this to generate the initial lock file.
      devShells.poetry = pkgs.mkShellNoCC {
        packages = [
          pkgs.poetry
        ];
      };
    })) // {
      overlays.default = import ./pkgs { inherit self inputs; };
      
      # For debugging
      inherit self;
    };
}
