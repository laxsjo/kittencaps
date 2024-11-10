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

_edit-icon-inner name editor:
    #!/usr/bin/env bash
    if [[ ! -f assets/icons/[{{name}}].svg ]]; then
        just create-icon {{name}};
    fi
    if [[ "{{editor}}" == "boxy-svg" ]]; then
        if ! command -v flatpak; then
            echo "Flatpak not installed."
            echo "If you want to edit icons using BoxySVG you need to install it using flatpak."
            exit 1
        fi
        if ! flatpak info com.boxy_svg.BoxySVG > /dev/null 2> /dev/null; then
            echo "BoxySVG is not installed."
            echo "If you want to edit icons using BoxySVG you need to install com.boxy_svg.BoxySVG using flatpak."
            exit 1
        fi
        
        flatpak run --filesystem=/nix/store --env=XDG_DATA_DIRS="$XDG_DATA_DIRS" --file-forwarding com.boxy_svg.BoxySVG @@ "assets/icons/[{{name}}].svg" @@ 2> /dev/null &
    else
        "{{editor}}" "assets/icons/[{{name}}].svg" 2> /dev/null &
    fi

generate-keycaps layout="moonlander-mk1" theme="standard":
    python -m src.package_keycaps \
        ./assets/layouts/{{layout}}.json \
        --theme=./assets/themes/{{theme}}.json \
        --out=./generated/{{layout}}_{{theme}}.svg
