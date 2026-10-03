# Style Guide — wuxia-3d-stylized

The single source of truth for how the film looks. Every renderer, every
generated asset, every camera decision reads from here. Change a value, and
every shot changes with it.

Nothing in this pipeline may roll dice at render time. Two runs on the same
inputs must produce byte-identical frames.

## Target look

Stylized 3D, closer to puppet theatre than photoreal CG:

- **Read first, detail second.** Silhouette and colour carry the shot. Surface
  detail is deliberately low so it does not compete.
- **Flat-ish shading, soft shadows.** Form is communicated by value blocks,
  not by texture.
- **Saturated accent against muted base.** The world is desaturated earth and
  stone; only cultivation energy and character accents are allowed to be vivid.
- **Consistent scale.** Human ≈ 1.75 m. Buildings follow the archetype table.

## Palette

| Role | Value | Use |
|---|---|---|
| Base earth | (0.38, 0.34, 0.30) | ground, architecture |
| Base stone | (0.42, 0.40, 0.36) | sect courtyards, walls |
| Base foliage | (0.30, 0.36, 0.28) | wilderness, bamboo |
| Accent jade | (0.45, 0.95, 0.70) | realm 3-4 aura |
| Accent violet | (0.70, 0.50, 1.00) | realm 5-6 aura |
| Accent gold | (1.00, 0.82, 0.35) | realm 7-8 aura |
| Accent white | (1.00, 1.00, 1.00) | realm 9 aura |

Nothing outside this list may appear as a deliberate accent.

## Location archetypes

Each place type maps to exactly one archetype, so a location never changes
shape between shots.

| Place type | Archetype | Ground | Notes |
|---|---|---|---|
| `สำนัก` | `sect_courtyard` | (0.42, 0.40, 0.36) | symmetrical, axial |
| `เมือง` | `town_street` | (0.38, 0.34, 0.30) | street runs toward vanishing point |
| `ตลาด` | `market_stall` | (0.44, 0.36, 0.28) | stalls frame the sides, open centre |
| `ลานฝึก` | `training_ground` | (0.40, 0.42, 0.34) | open, ring-shaped, no roof |
| `แหล่งวัตถุดิบ` | `wilderness` | (0.30, 0.36, 0.28) | irregular, no architecture |
| `แดนต้องห้าม` | `forbidden` | (0.22, 0.16, 0.24) | bruised violet, oppressive |
| `ประตูมิติ` | `realm_gate` | (0.30, 0.28, 0.40) | single vertical accent |
| `ด่านชายแดน` | `border_pass` | (0.40, 0.38, 0.34) | horizontal, windswept |
| `แดนลับ` | `hidden_lair` | (0.26, 0.22, 0.20) | enclosed, low ceiling |

## Camera

| Shot size | Focal length | Distance | Orbit | Eye height | f-stop |
|---|---|---|---|---|---|
| `establish` | 24 mm | 34 m | 25° | 9.0 m | 8.0 |
| `wide` | 35 mm | 20 m | 35° | 6.0 m | 5.6 |
| `medium` | 50 mm | 8 m | 20° | 2.4 m | 2.8 |
| `close` | 85 mm | 2.6 m | 8° | 1.65 m | 1.8 |

## Lighting by phase

| Phase | Hours | Sun elevation | Mood |
|---|---|---|---|
| `dawn` | 5-7 | 6° | low warm rim |
| `day` | 7-17 | 42° | neutral, high key |
| `dusk` | 17-21 | 8° | long orange shadows |
| `night` | 21-5 | -0.35° | moonlit, cool, low key |

## Character construction

Characters are **permanent, shared assets**. One model per `model_id`, reused in
every shot. This is the mechanism that prevents a face from changing between
cuts — the single most important rule in this document.

A model is built from parameters only, never from randomness:

| Parameter | Values | Source |
|---|---|---|
| `gender` | `ชาย` / `หญิง` | sim |
| `age_group` | `adult` / `elder` | age >= 60 |
| `build` | `slight` / `average` / `heavy` | fixed per model_id |
| `realm` | 0-9 | sim → aura only |
| `role` | blade, spear, staff, scholar, trade, healer, craft, travel | `character_art.py` |

Body proportions are fixed constants (see `PROPORTIONS` in the generator), not
per-model variation. Stylized characters gain character from silhouette and
colour, not from anatomical variation.

Height: adult 1.75 m, elder 1.68 m, beast 0.75×. These are the same values the
renderer assumes — they must not diverge.

## What an asset must satisfy

1. Loads in Blender 5.2 and exports to `.glb`
2. Origin at feet, facing +Y, standing on Z=0
3. Height within ±2% of the table above
4. Renders identically on repeated runs (no RNG, no time-seeded noise)
5. Single flat material per body region — no textures required to read correctly
