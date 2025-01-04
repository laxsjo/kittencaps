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
        config = {
          allowUnfree = true;
        };
      };
      pypkgsBuildRequirements = {
        coloraide = [ "hatchling" ];
        fake-bpy-module-4-2 = [ "setuptools" ];
      };
      poetryOverrides = (lib.mkPoetry2nixOverrides pypkgsBuildRequirements).extend
        (final: prev: {
          # Override with the one from nixpkgs, since it does some special
          # patches to avoid `playwright install`, which I don't know how to
          # replicate via poetry. 
          playwright = pkgs.python312Packages.playwright;
        });
      
      pythonEnv = (pkgs.poetry2nix.mkPoetryEnv {
        overrides = poetryOverrides;
        projectDir = self;
        python = pkgs.python312;
      });
      pythonApp = pkgs.poetry2nix.mkPoetryApplication { projectDir = ./.; };
      # Override python version used by blender to match project. This is
      # probably a very bad idea but I don't care. :3
      blender = (pkgs.blender.override {
        python3Packages = pkgs.python312Packages;
      }).overrideAttrs {
        # This disables the python version check.
        preConfigure = "";
      };
      devPackages = [
        pythonEnv
        pkgs.poetry
        pkgs.just
        pkgs.open-gorton
        blender
      ];
    in {
      lib = pkgsNoOverlay.callPackage ./lib.nix {};
      inherit pythonEnv;
      packages = {
        inherit (pkgs) open-gorton;
        scripts = pythonApp;
      };
      apps = {
        generate_icon = {
          type = "app";
          program = "${pythonApp}/bin/generate_icon";
        };
        package_keycaps = {
          type = "app";
          program = "${pythonApp}/bin/package_keycaps";
        };
      };
      devShells = {
        default = pkgs.mkShellNoCC {
          packages = devPackages ++ (with pkgs; [
            pureref
            inkscape
          ]);
          
          shellHook = ''
            export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
          '';
        };
        no-editors = pkgs.mkShellNoCC {
          packages = devPackages;
        };
        # Dev shell with only poetry. Use this to generate the initial lock file.
        poetry = pkgs.mkShellNoCC {
          packages = [
            pkgs.poetry
          ];
        };
      };
    })) // {
      overlays.default = import ./pkgs { inherit self inputs; };
      
      # For debugging
      inherit self;
    };
}
