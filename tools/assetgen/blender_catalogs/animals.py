"""Wildlife (ADR-0027): deer and hare on the quadruped skeleton (animal_quad), and the birds the
flocks instance (animal_bird). Ids are models/animals/<id>.glb; data/wildlife/*.json names them.
The Hollowed hounds (DESIGN §6) are quadrupeds too, with the Hollowed's action names."""
from __future__ import annotations

from ..core.registry import Task, blender_sources

QUADS = {
    # A white-tailed doe in her grey-brown autumn coat.
    "deer_doe": {"seed": 11, "species": "deer", "scale": 1.0, "bulk": 1.0,
                 "budget": {"body": 11000, "ears": 900},
                 "materials": {"fur": "fur_deer", "hoof": "hoof", "mouth": "nose_wet", "eye": "eye_animal"}},
    # A buck in the rut: bigger, a thick neck and brisket, an eight-point rack.
    "deer_buck": {"seed": 12, "species": "deer", "scale": 1.07, "bulk": 1.15, "antlers": {"tines": 3, "size": 1.0},
                  "budget": {"body": 11000, "ears": 900, "antlers": 2600},
                  "materials": {"fur": "fur_deer_buck", "hoof": "hoof", "mouth": "nose_wet", "eye": "eye_animal",
                                "antler": "antler"}},
    # A snowshoe hare, still brown in the autumn.
    "hare": {"seed": 21, "species": "hare", "scale": 1.0,
             "budget": {"body": 5200, "ears": 500},
             "materials": {"fur": "fur_hare", "hoof": "fur_hare", "mouth": "nose_wet", "eye": "eye_animal"}},
    # Hollowed hounds: Bloom-infected dogs starved to the bone, lips drawn back off the teeth, milky
    # eyes, the Bloom's shelf plates breaking out along the spine, the shoulders and one flank.
    # A rangy lab/hound mongrel, 0.62 m at the withers, drop ears (the left one torn).
    "hollow_hound_a": {"seed": 41, "species": "hound", "breed": "mongrel", "scale": 1.0, "bulk": 1.0, "gaunt": 1.0,
                       "ears": "drop", "torn_ear": "L", "grid": 0.0042,
                       "growth": {"spine": 5, "shoulder": 2, "flank": 5, "flank_side": "R"},
                       "budget": {"body": 10500, "ears": 700, "teeth": 1400, "growths": 3800},
                       "materials": {"fur": "fur_hound_a", "hoof": "hoof", "nose": "nose_wet", "mouth": "hound_gums",
                                     "eye": "eye_hound_milky", "teeth": "teeth", "gums": "hound_gums",
                                     "plates": "hound_bloom_plates", "threads": "bloom_growth"}},
    # A big shepherd-type, 0.70 m at the withers: a heavier chest, black saddle and mask, pricked
    # ears (the right one torn), the Bloom down its left flank.
    "hollow_hound_b": {"seed": 42, "species": "hound", "breed": "shepherd", "scale": 1.13, "bulk": 1.18, "gaunt": 0.85,
                       "ears": "erect", "torn_ear": "R", "grid": 0.0042,
                       "growth": {"spine": 6, "shoulder": 2, "flank": 6, "flank_side": "L"},
                       "budget": {"body": 11000, "ears": 700, "teeth": 1400, "growths": 4200},
                       "materials": {"fur": "fur_hound_b", "hoof": "hoof", "nose": "nose_wet", "mouth": "hound_gums",
                                     "eye": "eye_hound_milky", "teeth": "teeth", "gums": "hound_gums",
                                     "plates": "hound_bloom_plates", "threads": "bloom_growth"}},
    # Grey wolves (ADR-0055): the hound's rig and clips on a healthy animal, no Bloom. A grey
    # female of ~0.76 m at the withers, and a bigger, browner male (~0.82 m) with a heavier ruff.
    "wolf_a": {"seed": 51, "species": "hound", "breed": "wolf", "scale": 1.22, "bulk": 1.08, "gaunt": 0.12,
               "ears": "erect", "torn_ear": "none", "grid": 0.0042,
               "budget": {"body": 11500, "ears": 700, "teeth": 1400},
               "materials": {"fur": "fur_wolf_a", "hoof": "hoof", "nose": "nose_wet", "mouth": "nose_wet",
                             "eye": "eye_wolf", "teeth": "teeth", "gums": "hound_gums"}},
    "wolf_b": {"seed": 52, "species": "hound", "breed": "wolf", "scale": 1.32, "bulk": 1.2, "gaunt": 0.1,
               "ears": "erect", "torn_ear": "none", "grid": 0.0042,
               "budget": {"body": 11500, "ears": 700, "teeth": 1400},
               "materials": {"fur": "fur_wolf_b", "hoof": "hoof", "nose": "nose_wet", "mouth": "nose_wet",
                             "eye": "eye_wolf", "teeth": "teeth", "gums": "hound_gums"}},
}

BIRDS = {
    # A small brown songbird with a streaked breast: thrush and sparrow flocks in the canopy.
    "songbird": {"seed": 32, "kind": "songbird", "length": 0.2, "span": 0.32, "shoulder": 0.014,
                 "budget": {"body": 900}, "materials": {"feathers": "feathers_songbird", "beak": "beak", "eye": "eye_animal"}},
    # A crow: glossy black, fingered primaries.
    "crow": {"seed": 31, "kind": "crow", "length": 0.46, "span": 0.95, "fingers": 5, "shoulder": 0.035,
             "budget": {"body": 1600}, "materials": {"feathers": "feathers_crow", "beak": "beak_crow", "eye": "eye_animal"}},
}


def tasks() -> list[Task]:
    out = []
    for key, p in QUADS.items():
        rel = f"models/animals/{key}.glb"
        out.append(Task(name=f"model:animals/{key}", group="models", outputs=[rel], sources=blender_sources("animal_quad"),
                        params={"name": key, **p}, blender="animal_quad",
                        imports={rel: {"type": "scene", "animation": True}}))
    for key, p in BIRDS.items():
        rel = f"models/animals/{key}.glb"
        out.append(Task(name=f"model:animals/{key}", group="models", outputs=[rel], sources=blender_sources("animal_bird"),
                        params={"name": key, **p}, blender="animal_bird", imports={rel: {"type": "scene", "lods": False}}))
    return out
