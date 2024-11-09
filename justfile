help:
    just --list

# Generate the assets/icons/icon-template.svg file
create-icon-template:
    nix build .#icon-template-svg
    cp --no-preserve=mode,ownership,timestamps result assets/icons/icon-template.svg

# Create a new icon with the specified name in assets/icons
create-icon name:
    cp assets/icons/icon-template.svg assets/icons/[{{name}}].svg
    @echo "Created 'assets/icons/[{{name}}].svg', edit it by running 'just edit-icon {{name}}'"

# Open icon `name` in the specified editor, with the required Open Gorton font installed.
edit-icon name editor="inkscape":
    nix develop -c just _edit-icon-inner "{{name}}" "{{editor}}"

_edit-icon-inner name editor="inkscape":
    if [[ ! -f assets/icons/[{{name}}].svg ]]; then \
        just create-icon {{name}}; \
    fi
    {{editor}} assets/icons/[{{name}}].svg 2> /dev/null &

generate-keycaps layout="moonlander-mk1" theme="standard":
    python -m src.package_keycaps \
        ./assets/layouts/{{layout}}.json \
        --theme=./assets/themes/{{theme}}.json \
        --out=./generated/{{layout}}_{{theme}}.svg
