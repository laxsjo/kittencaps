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

## Credits
Key template from https://github.com/Maximillian/keycap-set-templates/
