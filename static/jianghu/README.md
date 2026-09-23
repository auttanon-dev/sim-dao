# River inn observer scene

Open `/jianghu` through the existing Python dashboard. This is a local, read-only viewer.

## Finished slice

- The approved river-town artwork is now a background plate with all baked-in people removed through ImageGen.
- Actual living, visible residents of the inn are overlaid using the approved transparent character concept atlas. The same character ID retains its art assignment across refreshes.
- Camera drag, cursor-centered zoom, click selection, portraits, following within the scene, full-scene viewing, evening/night lighting, lamp glow, river shimmer and falling petals are implemented.
- Data refreshes every 15 seconds. Hidden tabs suspend rendering/polling. Reduced-motion preference pauses ambient animation by default.
- Missing artwork or missing data gets an explicit error; no invented residents or events are substituted. Missing saves use the existing labelled seeded preview.
- Other locations retain the real map, residents and local events. They do not yet have individual art scenes.

## Presentation versus simulation

Only the inn is mapped to the finished art plate. Actor positions, appearance variants, breathing and short ambient walking paths are presentation choices; they are not simulation coordinates or new logged events. Resting/sleeping characters remain stationary. Moving states use a static cutout with subtle bobbing, not a finished multi-direction walking animation. At most 32 people are drawn; all local residents remain available in the list.

This page does not advance, start, pause, save or modify the simulation. Its pause controls apply to visual animation and snapshot refresh only. The simulation must already be running elsewhere if live world progression is wanted. Following currently stays within the selected scene; it does not follow someone across locations.

## Assets

- `river-inn.png`: 1672 × 941. ImageGen edit of `art-preview/river-town-v1.png`, removing every person and preserving composition and lighting. Generated 2026-09-10, source `exec-4f645a3b-ebb5-44a5-9a7f-25d1e619b828.png`.
- `characters.png`: unchanged copy of `art-preview/character-concepts-v1.png`, RGBA 1254 × 1254. Canvas source rectangles display each concept; original files are retained.
- `characters-martial.png` and `characters-civilian.png`: RGBA 1254 × 1254, four columns by two rows (top row men, bottom row women). Source rectangles in `character-art.json` are the measured alpha bounding box of each cell plus 12 px padding, clamped to the cell.
- `characters-elders.png` (Sheet 3 in `art-preview/character-atlases-prompts.txt`) has **not** been generated. Until it exists, the eight elder catalogue entries borrow a gender- and role-matched cell from the two sheets above and carry `"art_pending": "characters-elders.png"`. Replacing them is a per-entry edit of `sheet`, `cell` and `source`; nothing else has to change.

`character-art.json` is the single source of truth for which atlases exist: `jianghu_routes.asset_names()` serves exactly the sheets it names, and `CHARACTER_SHEETS` in `scene-model.mjs` must list the same set (a sheet missing there is silently dropped by the renderer, which then falls back to `characters.png`).

Approved source prompts are in `art-preview/prompts.md`. Background edit brief: remove all people/characters; preserve scene composition, buildings, props, river, mountains, light and HD-2D texture; reconstruct empty ground.

## Validation

`python -m unittest test_jianghu_view`

`node --test tools/test_jianghu_scene.mjs`

These check read-only behavior, locality, asset routes, unavailable locations, camera geometry, picking and stale request cancellation. Browser visual testing has not been run for this slice.
