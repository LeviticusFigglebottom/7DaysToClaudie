"""Wildlife (ADR-0027): deer and hare on the quadruped skeleton (animal_quad), and the birds the
flocks instance (animal_bird). Ids are models/animals/<id>.glb; data/wildlife/*.json names them."""
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
