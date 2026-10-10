# Ezra's gear by state (TD-302)

* `camp_night_fighting.webp`: Godot, real materials (compatibility renderer under xvfb), `preview_asset --hide` showing what the game shows in each state. At his camp (`sit_injured`): the splint on his left leg and the hatchet on his belt. Following at night (`idle`, 21:00): the hurricane lantern in his left hand. Fighting (`attack_a`): the hatchet in his fist.
* `belt_hatchet.webp`: the hatchet hung head up from his belt on the right hip (Godot).
* `blender_belt_and_splint.webp`: flat Blender renders of the belt hatchet from his right side and back, and the splint from his left.

The props are separate skinned meshes (prop_hatchet_hand, prop_hatchet_belt, prop_lantern, prop_splint), shown by CompanionMind._props through EnemyVisual.set_part. Not checked on a GPU.
