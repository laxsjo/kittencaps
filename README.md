# Kittencaps

TODO

## Editing icons

This project is designed to support editing the icon SVGs with Inkscape and BoxySVG. Other editors may work however.
TODO: Add notes about installing BoxySVG, and making sure to place all elements in the child svg element.


## Development
```sh
nix develop
poetry install
```
Now you should be able to select the interpreter in VS Code.

TODO: Add note about how this installs versions of the different editors/other GUI programs, and how there is a `.#no-editors` development environment which does not.

Run using
```shell
nix run .#package
nix run .#generate_icon -- [args]
```

or

```shell
nix develop
python -m src.package
python -m src.generate_icon [args]
```

### PureRef
This project has a collection of reference images managed using PureRef. It requires some extra care to install using nix. To be able to run `nix develop` (which will try to install PureRef), you first need to go to [PureRef's download page] and download version 2.0.3 as an .appimage (select Linux > Portable). Then run
```shell
nix-store --add-fixed sha256 ~/Downloads/PureRef-2.0.3_x64.Appimage
```
after which `nix develop` should be able to build properly.

You can then open the reference image board using `pureref references/references.pur`

## Credits
Key template from https://github.com/Maximillian/keycap-set-templates/
keycap 3D models from https://www.thingiverse.com/thing:2172302 (CC BY-NC-SA)
Moonlander mk1 case 3D model from https://www.zsa.io/moonlander/printables (license is IDK, but it's probably fine...)
