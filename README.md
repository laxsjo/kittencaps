# Kittencaps

TODO

## Development
```sh
nix develop
poetry install
```
Now you should be able to select the interpreter in VS Code.

Run using
```shell
nix run .#package
nix run .#generate_embedded_font_svg -- [args]
```

or

```shell
nix develop
python -m src.package
python -m src.generate_embedded_font_svg [args]
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
