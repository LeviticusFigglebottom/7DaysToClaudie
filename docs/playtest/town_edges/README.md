# Town edges (owner report 4: "bare town edges, little grass, no trees")

GL renders (`make screenshots`, the OpenGL fallback: no lavapipe in that container; stand-in models,
no `make assets`) of the shots `pell_edge_aerial` and `pell_edge_west` before and after 391bd97:

* **before**: D6's meadow circle (175 m round (-60, 2100)) kept trees to a third of the forest's
  for 50 m round Pell's Crossing, and the `town` biome on its pad grew 9.9 ground plants per
  100 m2 (the meadow outside 25-34) and nothing else.
* **after**: the meadow is 120 m over a 215 m second-growth birch circle, and the `town` biome grows
  long grass, yarrow, fireweed, a few huckleberry, saplings and birch. Inside the pad ground plants
  9.9 -> 17.5 and bushes 0.12 -> 0.33 per 100 m2; trees 0-50 m out 0.88-1.04 -> 1.05-1.62.

`pell_west_end_edge_c6_planned.jpg`: Pell's west end from (-735, 2140). C6 is a `planned` region, so
only its coarse far terrain streams: no houses (32 of the west end's 36 lots stand in C6), no grass,
the impostor forest faded out round the camera.
