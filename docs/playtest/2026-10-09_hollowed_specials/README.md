# Hollowed specials and the dirt layer (TD-192, round 4)

* `shelves_before_after.webp`: Bloom shelves, flat fans (left) against lobed, domed caps with a rolled lip and gill ribs (right), seen from above and from below. Flat Blender renders.
* `husk_seams_before_after.webp`: the Husk's plate seams, with big growth blobs before and small knots under the rims after.
* `rammer_yoke_before_after.webp`: the Rammer's yoke. The shoulder cut no longer slices a gore cap through it.
* `keener_sac_before_after.webp`: the Keener's sac as a thick throat before (left) and as a bulb under the jaw after.
* `dirt_layer_godot.webp`: Godot (compatibility renderer under xvfb), the torsos with dirt as its own layer (vertex A) and blood only at wounds, mouths and hands. This shot uses skin dirt 1.0; skin_hollow is now at 0.75.

Not checked on a GPU or at night with `bloom_glow`.

## A mixed group at dusk, 10 / 20 / 30 m

`crowd_dusk_10_20_30m.webp` (full frames left, centre crops right, enlarged nearest-neighbour so the pixels are the real ones), and the full frames `crowd_dusk_<d>m.webp`. Made with `src/tools/cli/crowd_shot.gd`: eight plain Hollowed (hollow_a..d, cordon, hunter, nurse, lurcher_b) in a loose group, each with its own skin tone (instance_variation) and idle moment, at 19:00 under a low sun. The eye is at 1.65 m with a 60° field of view, 1280x720.

This is a staged scene (sky, sun, fog, flat ground), not the streamed world, and the compatibility renderer under xvfb (no subsurface scattering). The game's dusk on a GPU will differ.

Reading: at 10 m the group reads as eight different people by clothes, build, posture and hair, with tone differences visible. At 20 m clothes and silhouettes still separate them. At 30 m it is mostly colour blocks and height. Faces are not legible past ~10 m at 720p.
