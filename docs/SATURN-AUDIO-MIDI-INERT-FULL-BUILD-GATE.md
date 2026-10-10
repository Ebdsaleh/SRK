# Saturn Audio MIDI Inert Full-Build Gate

This gate is the next step after the real legacy SH-ELF compiler accepted
`srk_saturn_midi_generated.c` in isolation.

It still does **not** enable MIDI playback on Saturn hardware.

## Goal

Prove that the complete, already-working standalone diagnostics image can be
compiled, linked, ISO-packaged, MODE1/2352-packaged, and provenance-verified
while the deterministic MIDI event/tone data is present in the final binary.

The gate deliberately derives from the accepted Stage 6B Gate 5 project rather
than rebuilding or editing that baseline.

## Baseline

Expected accepted baseline:

```text
C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5
```

The gate requires:

- a `srk.saturn.standalone-project.v1` manifest;
- a successful `srk.saturn.standalone-build.v1` report;
- exact build-report -> manifest SHA-256 agreement;
- every manifest-pinned generated input still matching its size and SHA-256.

If any baseline input has changed, the gate refuses to continue.

## Fresh derivation

Only manifest-pinned generated inputs are copied to a fresh off-card directory.
Old build outputs, build logs, and build reports are not copied.

The gate then:

1. copies `srk_saturn_midi_generated.c` and `.h` into the fresh `src` tree;
2. appends the generated inert C data to the copied
   `srk_saturn_runtime.c` translation unit;
3. records the exact source/header hashes and baseline manifest hash;
4. rebuilds the complete generated-input inventory;
5. runs the normal Python-native standalone builder unchanged.

Appending to the copied runtime translation unit is intentionally a **gate-only
compile/link proof**. It avoids changing the production standalone file lists
until the complete build is proven on the user's real legacy toolchain.

## Inert safety contract

The gate manifest explicitly records:

```text
midi_bridge_active       false
midi_sound_ram_writes    false
midi_scsp_mmio           false
midi_mc68ec000_execution false
```

There is:

- no new menu/control chord;
- no MIDI event dispatcher;
- no Sound RAM mailbox initialization;
- no SCSP slot change;
- no MC68EC000 program replacement;
- no SAROO write;
- no physical Saturn write.

The resulting BIN/CUE is an **off-card evidence artifact only**.

## Source gate

After pulling the tranche, run:

```bat
cd /d C:\Users\Developer.ERIDU\repos\Python\SRK
.venv\Scripts\activate

git status
git pull --ff-only
git log -4 --oneline
git rev-parse HEAD

python -m unittest discover -s tests -p "test_*.py"
python -m pytest -q
python -m pytest
```

The tranche adds four tests. Expected total:

```text
455 tests
```

## Full off-card build gate

Only after the source gate is green, run:

```bat
python -m rikai_kotoba.tools.saturn_midi_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-INERT-FULL-GATE1"
```

The output directory must not already exist.

Success boundary:

```text
Bridge active    : NO
Result          : SUCCESS
The complete standalone image built with the inert MIDI bridge compiled and linked in.
No MIDI hardware launch, SAROO write, Sound RAM write, or SCSP write was performed.
```

The normal standalone builder must also show all compile/assembly/link/ISO and
MODE1/2352 steps succeeding.

Preserve the entire gate tree whether the result succeeds or fails.

## After success

A successful full gate proves:

```text
canonical SMF
  -> SRK parser/scheduler
  -> SRKM event program
  -> deterministic Saturn tone bank
  -> C89 generated bridge
  -> legacy SH-ELF compile
  -> complete standalone link
  -> complete ISO
  -> verified MODE1/2352 BIN/CUE
```

Only then should the generated MIDI C/H be promoted into the normal production
standalone project/build lists.

Even after that promotion, the bridge remains inert until a separately reviewed
SH-2 <-> MC68EC000 mailbox consumer is introduced.

No R18 SAROO deployment is authorized by this gate.
