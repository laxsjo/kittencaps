editor := `if [[ -f .svg-editor ]]; then cat .svg-editor; else printf "boxy-svg"; fi`

help:
    just --list

# Define the editor used by edit-icon. Writes the given value to the hidden .svg-editor file. Either a path to an executable, an executable on you're path, or "boxy-svg", which will execute the flatpak (which needs to be installed for it to work). 
set-editor $new_editor:
    printf "%s" "$new_editor" > .svg-editor
    @echo "Just edit-icon will now open '$new_editor'"

bg-color := "bg_main"
margin := "10"

# Create a new icon with the specified name in assets/icons. Size should be in u, may specify two dimensions for vertical keycaps, override the bg-size variable, which must be a valid color name from the standard theme. You can override the `margin` variable. See `python -m src.generate_icon --help` for more details.
create-icon name size="1u":
    nix build .#open-gorton
    python -m src.generate_icon \
        --size {{size}} \
        --bg-color "{{bg-color}}" \
        --margin "{{margin}}" \
        --out "assets/icons/[{{name}}].svg" \
        --font result/share/fonts/opentype/OpenGorton-Regular.otf \
        --font result/share/fonts/opentype/OpenGorton-Bold.otf
    @echo "Created 'assets/icons/[{{name}}].svg', edit it by running 'just edit-icon {{name}}'"

# Calculate the position of a text line's baseline, such that the character 'H' is visually centered in a box with the given height.
calculate-centered-text-pos height font-family font-size font-weight:
    python -m src.calculate_centered_font_pos --height "{{height}}" --family "{{font-family}}" --font-size "{{font-size}}" --weight "{{font-weight}}"

# Open icons with the given `names` in the configured editor (You can configure it via `just set-editor ...`, or by overriding the `editor` variable, i.e. `just editor=... edit-icon icon`). Make sure to have ran nix develop before, so that Open Gorton is installed.
edit-icon +$names:
    #!/usr/bin/env bash
    for icon in $names; do    
        if [[ ! -f "assets/icons/[$icon].svg" ]]; then
            echo "Warning: icon '$icon' does not exit. Run 'just create-icon $icon' to create it!"
        else
            if [[ "{{editor}}" == "boxy-svg" ]]; then
                if ! command -v flatpak; then
                    echo "Flatpak not installed."
                    echo "If you want to edit icons using BoxySVG (the default) you need to install it using flatpak."
                    exit 1
                fi
                if ! flatpak info com.boxy_svg.BoxySVG > /dev/null 2> /dev/null; then
                    echo "BoxySVG is not installed."
                    echo "If you want to edit icons using BoxySVG (the default) you need to install com.boxy_svg.BoxySVG using flatpak."
                    exit 1
                fi
                
                flatpak run --filesystem=/nix/store --env=XDG_DATA_DIRS="$XDG_DATA_DIRS" --file-forwarding com.boxy_svg.BoxySVG @@ "assets/icons/[$icon].svg" @@ 2> /dev/null &
            else
                "{{editor}}" "assets/icons/[$icon].svg" 2> /dev/null &
            fi
        fi
    done

generate-keycaps layout="moonlander-mk1" theme="standard":
    python -m src.package_keycaps \
        ./assets/layouts/{{layout}}.json \
        --theme=./assets/themes/{{theme}}.json \
        --out=./generated/{{layout}}_{{theme}}

# TODO: This command should save the hashes of it's inputs, and only generate a new .blend file if it changes, since creating the blend file is non-deterministic.
generate-render-scene layout="moonlander-mk1" theme="standard":
    BLENDER_SYSTEM_PYTHON="$VIRTUAL_ENV" PYTHONPATH="$(python -c "import sys; print(\":\".join(sys.path))")" blender \
        assets/templates/render/scene-template.blend \
        --background \
        --python "src/blender/assemble_render_keyboard.py" -- \
        --directory ./generated/moonlander-mk1_standard/ \
        --out ./generated/moonlander-mk1_standard/scene.blend

# Update the palette colors in the specified icon SVG files to match the colors defined in the standard theme. The icon names should be the text in between the [brackets], i.e. to update assets/icons/[tab].svg run `just update-icon-palettes tab`. Default is to update all icons.
update-icon-palettes *icons="*":
    python -m src.update_icon_palettes '{{icons}}' \
        --theme=./assets/themes/standard.json

# Synchronies all generated assets and update icon SVG file colors. Essentially a wrapper around `generate-keycaps` and `generate-render-scene` but for all theme and layout variations, and finally running `update-icon-palettes`. You should essentially run this before every commit to make sure all files are updated. Take note of reverting the generated blend file if none of the input files changed, since unfortunately saving .blend files is non-deterministic, meaning they will always be marked as changed.
sync:
    python -m src.sync

# Open the reference images in pureref
open-refs:
    pureref references/references.pur &>> /dev/null &
