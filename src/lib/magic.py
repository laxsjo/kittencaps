from decimal import Decimal

# Collection of all magic numbers in this project

# Extra whitespace around generated keymap in pixels.
padding = 40

# The width of the 1u keycap 3D model in blender units.
# Apparently the usual spacing is 19.05 mm according to:
# https://deskthority.net/viewtopic.php?p=327500&sid=cbe1f55d9be4c1624f7ea9218f7986ee#p327500
# But the official Moonlander 3D model has 19 mm as the spacing.
keycap_model_unit_size = float(Decimal("19") / 1000)
