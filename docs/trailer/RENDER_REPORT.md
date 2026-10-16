# Hollowmere trailer render report (2026-10-16)

Worktree `C:\Users\Aaron\Documents\GitHub\7dtc-trailer`, branch `local/trailer-render` @ 2e42f61b for the first pass. The follow-up pass (at the end) is committed locally as 54615134 and 36d920bc. Nothing pushed.
Everything ran natively on Windows 10 (WSL is broken), throttled to affinity 0xFFF000 (12 of 24 logical CPUs) and BelowNormal priority, one job at a time.

## Route and where each step ran
| Step | How | Where |
|---|---|---|
| Blender 5.2.2 check | `blender.zip` SHA-256 `3849d17a…b535` matches the official `blender-5.2.2.sha256` (windows-x64.zip); all 6525 extracted files match the zip's sizes | CPU |
| Existing assets check | 1457 recorded tasks / 3994 outputs re-hashed against manifest: 0 missing/empty/mismatched | CPU |
| `tools/build_assets.py --jobs 8 --blender .tools\blender\blender.exe` | resumed: 421 of 1878 tasks built, 0 failed, 1732 s | CPU (by design) |
| Godot import (`--headless --import`) + `verify_imports.gd` | 770 s; verify exit 0 (no re-import needed) | CPU |
| Bake (`bake.gd`, `--rendering-driver vulkan`) | 8 species, 50 s | **GPU** |
| Import, then stills (`stills.gd --shot menu` / `wreck`) | menu_0..4 in 26 s, intro_wreck in 152 s; moved into `game/assets/generated/stills` with the same `.import` sidecars and stamps as `tools/stills.sh` | **GPU** |
| Import, then previews and Movie Maker renders, one shot at a time | see below | **GPU** |
| `trailer_cut.py`, `trailer_sheet.py`, ffmpeg 9.0.2 (already installed via winget) | | CPU |

## GPU confirmation
Every rendered run logged: `Vulkan 1.4.349 - Forward+ - Using Device #0: AMD - AMD Radeon RX 9070 XT`.

## Shots (1920x1080, 30 fps)
| Shot | Frames | s/frame | Shot render | Whole run (load + stream + warm + shot) |
|---|---|---|---|---|
| dawn_drone | 165 | 0.87 | ~144 s | 298 s |
| pell_crane | 150 | 0.77 | ~116 s | 256 s |
| horde_overhead | 120 | 0.52 | ~62 s | 243 s |

(Software Vulkan was ~19 s/frame per CLAUDE.md.)

## Exposure
`horde_overhead` kept `"exposure": 14.0`, **no change to shots.json**. On the GPU it is not blown out: mean luma 10-14 of 255, 0 % clipped pixels. The moonlit clearing and the horde read in the moonlight, and the rest is blue-black night. Lowering it would hide the horde.

## Underground check
All `TRAILER key` heights are positive: dawn_drone 34.0 / 28.0 / 24.0 m; pell_crane 1.8 / 12.0 / 32.0 m; horde_overhead 29.8 / 24.0 m.

## Outputs
- Shots: `build/trailer/shots/<id>/frame########.png` + `frame.wav` (raw frames deleted after cutting)
- MP4s: `build/trailer/dawn_drone.mp4`, `pell_crane.mp4`, `horde_overhead.mp4` (h264 crf 18 + aac)
- Contact sheet: `docs/playtest/2026-10-16_trailer_samples.jpg` (untracked)
- Previews: `build/trailer/preview/`; logs: `build/trailer/*.log`, `build/*.log`

## Problems and notes
1. **Movie Maker ignored `--resolution 1920x1080`** and recorded at 1280x720, because project.godot sets `window/size/window_width_override=1280` / `height=720`. Fix: a temporary, untracked `game/override.cfg` set the override to 1920x1080 during the renders, then I deleted it. The first 720p dawn_drone take was discarded and re-rendered. `tools/trailer_shot.sh` likely has the same problem on Linux.
2. Godot's stderr fills with `Couldn't get Vulkan surface capabilities (VkResult error -13)` (swapchain). Frames come from the viewport texture and are unaffected. One preview run died once with the window minimized; it re-ran fine with a normal window.
3. The game loads the user's own `%APPDATA%\hollowmere\settings.cfg` (graphics preset "ultra"), so the renders use ultra settings.
4. pell_crane around 1.7-2.3 s: a streetlight arm sweeps close past the lens as the crane rises, and the lamp head looks slightly detached from its arm. This is a framing and model nit, not a render fault.
5. Repo checks (`check`/`validate`/`test`) were not run on the trailer code. The 21 other clip ids still have no definitions.

---

# Follow-up pass (2026-10-16, 06:00-06:30)

Same throttle (affinity 0xFFF000, BelowNormal, one Godot/ffmpeg at a time, only own PIDs). Godot:
`C:\Users\Aaron\Tools\godot-4.7.2\Godot_v4.7.2-stable_win64_console.exe`. No `override.cfg` was used.

## Commands (Windows equivalents of tools/trailer_shot.sh)
- Preview: `godot --path game --rendering-driver vulkan --audio-driver Dummy --fixed-fps 30 -s res://src/tools/cli/trailer.gd -- --no-user-settings --shot <id> --preview --out build/trailer/preview/<tag>`
- Render: `godot --path game --rendering-driver vulkan --write-movie build/trailer/raw/<id>/frame.png --fixed-fps 30 -s res://src/tools/cli/trailer.gd -- --no-user-settings --shot <id>`,
  then `.tools\venv\Scripts\python.exe tools/trailer_cut.py <raw> build/trailer/shots/<id> <frames>`, then the raw frames are deleted,
  then `ffmpeg -framerate 30 -i frame%08d.png -i frame.wav -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 128k -shortest -movflags +faststart <id>.mp4`.
- Sheet: `python tools/trailer_sheet.py docs/playtest/2026-10-16_trailer_samples.jpg build/trailer/shots/{dawn_drone,pell_crane,horde_overhead}`.

## 1. horde_overhead exposure: 14 -> 36
| exposure | env tonemap exposure | mean luma (first / mid / last frame) | p99.5 | clipped |
|---|---|---|---|---|
| 14 (old render) | 17.5 | 12.1 / 12.5 / 15.3 | 77-79 | 0 % |
| 18 (preview) | 22.5 | 13.1 / 14.9 / 18.3 | 83-91 | 0 % |
| 22 (preview) | 27.5 | 15.9 / 17.8 / 21.8 | 94-103 | 0 % |
| 32 (preview) | 40.0 | 22.3 / 24.8 / 29.9 | 114-123 | 0 % |
| **36 (final render)** | 45.0 | **28.6 / 29.7 / 35.3** | 127-131 | **0 %** |

18 and 22 were still too dark (mean under 25). At 36 the moonlit clearing and the horde read clearly and the forest stays
blue-black: about 70-75 % of pixels are still below 32/255 and nothing goes above about 236. It looks like night, not day. Previews are in
`build/trailer/preview/exp18|exp22|exp32`.

## 2. Resolution and settings fix (commit 54615134, local)
- Cause confirmed: even with `--resolution 1920x1080` (the window really is 1920x1080 once scripts run), Movie Maker logged
  "recording movie in 1280x720" and wrote 1280x720 PNGs. It sizes frames from the window override at launch.
- Fix: `game/project.godot` gets `window/size/window_width_override.movie=1920` / `window_height_override.movie=1080`.
  The `movie` feature tag is active only under `--write-movie`, so normal play keeps 1280x720. A probe confirmed that Movie Maker now
  records 1920x1080. It works the same for `tools/trailer_shot.sh` under xvfb, and the `--resolution` flag, which had no effect, was removed from that script.
- The runner also renders the root viewport at 1920x1080 (content scale mode "viewport"), so previews match.
  It warns if Movie Maker's window isn't 1920x1080.
- `Settings` has an ephemeral mode: with `-- --no-user-settings`, `user://settings.cfg` is neither read nor written.
  `trailer_shot.sh` passes the flag, and the runner forces preset "ultra". That matches the user's current file, so
  dawn_drone (not re-rendered) still matches the other shots. The user's settings.cfg content is unchanged.

## 3. pell_crane: the camera, plus a small model gap
- Camera: the crane rose straight through the lamp head of the street lamp at framework (36.2, 106) (world ~(-75.8, 2110)),
  so the arm swept across the lens. Fixed by moving all three camera keys 4 m east (x -1/-3/-8 -> 3/1/-4), with looks unchanged
  (commit 36d920bc). After the re-render the lamp no longer enters the frame, and the composition is otherwise the same.
- Model (not fixed, out of scope): `street_lamp` in `tools/assetgen/blender/generators/props_ext_street.py` does have a gap.
  The arm tube ends (capped) at y = -1.60 and the head's rear tip starts at y = -1.63 with zero radius, which leaves about 3 cm of air
  between them. One-line fix: end `arm_pts` at about `(0, -1.75, H + 0.38)` so the arm runs into the head, then rebuild the
  three street_lamp variants and re-import.

## 4. Checks (Windows, headless, throttled)
- `check_scripts.gd` (make check): `[check] 523 scripts, 0 failed`.
- GUT `test_trailer_shots.gd`: 5/5 passed (24 asserts). `test_options.gd` (15/15) and `test_whats_new.gd` (4/4) also passed;
  they were run because `settings.gd` changed.

## Timings (RX 9070 XT, ultra)
horde_overhead 0.74 s/frame, 366 s whole run; pell_crane 0.78 s/frame, 286 s. dawn_drone was not re-rendered: its shot is unchanged and was already 1080p on ultra.

## Outputs
- `build/trailer/horde_overhead.mp4` (new), `build/trailer/pell_crane.mp4` (new), `build/trailer/dawn_drone.mp4` (unchanged); all 1920x1080.
- `docs/playtest/2026-10-16_trailer_samples.jpg` regenerated from all three shots (still untracked).
