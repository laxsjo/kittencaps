help:
    just --list

# Create a new icon with the specified name in assets/icons. Size should be in u, may specify two dimensions for vertical keycaps, and bg-size should be a valid color name from the standard theme. see `python -m src.generate_icon --help` for more details.
create-icon name size="1u" bg-color="":
    nix build .#open-gorton
    python -m src.generate_icon --size {{size}} --bg-color "{{bg-color}}" --out "assets/icons/[{{name}}].svg" \
        --font result/share/fonts/opentype/OpenGorton-Regular.otf \
        --font result/share/fonts/opentype/OpenGorton-Bold.otf
    @echo "Created 'assets/icons/[{{name}}].svg', edit it by running 'just edit-icon {{name}}'"

# Calculate the position of a text line's baseline, such that the character 'H' is visually centered in a box with the given height.
calculate-centered-text-pos height font-family font-size font-weight:
    python -m src.calculate_centered_font_pos --height "{{height}}" --family "{{font-family}}" --font-size "{{font-size}}" --weight "{{font-weight}}"

# Open icon `name` in the specified editor, make sure to have ran nix develop before, so that Open Gorton is installed.
edit-icon name editor="boxy-svg":
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
        --out=./generated/{{layout}}_{{theme}}

generate-render-scene layout="moonlander-mk1" theme="standard":
    BLENDER_SYSTEM_PYTHON="$VIRTUAL_ENV" PYTHONPATH="$(python -c "import sys; print(\":\".join(sys.path))")" blender \
        assets/templates/render/scene-template.blend \
        --background \
        --python "src/blender/assemble_render_keyboard.py" -- \
        --directory ./generated/moonlander-mk1_standard/ \
        --out ./generated/moonlander-mk1_standard/scene.blend

# Open the reference images in pureref
open-refs:
    pureref references/references.pur &>> /dev/null &
