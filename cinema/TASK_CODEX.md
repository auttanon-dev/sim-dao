# Task: procedural character generator

Write ONE new file: `cinema/make_character.py`

It generates a stylised wuxia character mesh in Blender from a parameter dict,
so that one `model_id` always produces one identical character.

## Rules (hard requirements)

1. **NO RANDOMNESS.** No `random`, no RNG, no time-based seed, no per-run
   variation. Same parameters must give a byte-identical mesh every run. This
   is the entire point of the pipeline.
2. **ASCII only in the .py file.** No em-dashes, no smart quotes, no non-ASCII
   comments. Blender's Python and the Windows console will choke on them.
3. Blender 5.2 compatible. Engine enum resolution must be loose (never hardcode
   `BLENDER_EEVEE_NEXT`; resolve from the live enum like `pick_engine` does).
4. Do NOT modify any existing file. Do NOT touch `tiandao/`. Only add
   `cinema/make_character.py` and the assets it writes.

## Read first

- `cinema/STYLE_GUIDE.md` — the look. Palette, camera, proportions, and the
  asset requirements a model must satisfy.
- `cinema/render_shot.py` — how assets are consumed. `BLOCKING_RESOURCES /
  "chars" / f"{model_id}.glb"` is where your output must land.

## What to build

A script with this interface:

    blender -b --factory-startup -P cinema/make_character.py -- \
        --model-id characters-elders-6 \
        --gender ชาย --age-group elder --build average --role blade \
        --out "D:\Sim Dao\cinema\assets\chars\characters-elders-6.glb"

Build the body from primitives and fixed `PROPORTIONS` constants (no texture
needed for it to read correctly — stylised, silhouette-first). Requirements:

- Height within 2% of: adult 1.75 m, elder 1.68 m
- Origin at the feet, facing +Y, standing on Z=0
- One flat material per body region, colours drawn only from the STYLE_GUIDE
  palette. Add one muted earth-tone for robes/clothing that is not in the accent
  list, and document it.
- `--role` should visibly change silhouette or costume (blade vs scholar vs
  healer must be distinguishable at a glance)
- Export to `.glb`

Also support `--manifest` to generate several characters at once from a list.

## Verify before you report done

Run it. Actually run Blender and export at least three:

    characters-elders-6  (elder, male, blade)
    characters-martial-0 (adult, male, blade)
    a female adult       (use a different model_id)

Then confirm each exported .glb exists and is non-trivial in size. Report the
actual file sizes you observed. Do not claim success without running it.

## Report back

- The file you wrote
- The three .glb files with their real sizes
- Anything in STYLE_GUIDE.md you think is wrong or ambiguous
