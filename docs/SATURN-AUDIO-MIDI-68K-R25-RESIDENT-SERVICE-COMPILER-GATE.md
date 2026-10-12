# Saturn Audio/MIDI — R25 Four-Slot Resident Service Compiler Gate

R24 physically proved complete playback of the 310-record CC0 reference MIDI.
The accepted R25 source model then established that a 120-ms release policy
fits a four-slot no-steal pool. This gate turns that model into inert generated
MC68EC000 program data and checks every legal SCSP release-rate field with the
legacy SH-ELF compiler before any value is selected or executed.

## Resident service contract

The R25 image derives from the accepted resident stream engine while keeping
the R23 and R24 binary hashes unchanged.

```text
owned SCSP slots       0..3
slot phases            FREE / HELD / RELEASING
release lifecycle      120000 us bounded ownership
Note Off               KEY_OFF; mixer remains unchanged
retirement             mixer zero + FREE only after deadline
allocation             matching key, then lowest free, no steal
program range          0x00004000..0x00009194
reviewed maximum       0x0000A000
voice ledger           0x00002300..0x000023FF
mixer table            0x00002400..0x000024FF
```

The service samples the same stable producer clock used by the scheduler while
waiting for records and while waiting for a new mailbox batch. This is required
to retire the final release tail even when no later MIDI record exists.

## Release-rate policy remains fail-closed

`release_rate` is a required generator input. The inert matrix renders RR
values 0 through 31, with exact EG1/EG2 words and a distinct image hash for
every value. Compilation proves representation compatibility only. It does not
select an RR value, measure a release, access SCSP MMIO, start the MC68EC000, or
write Saturn/SAROO media.

Physical measurements remain mandatory before one RR value can become policy.

## Eridu source tests

From the repository root:

```bat
python -m pytest -q ^
  tests/test_saturn_midi_68k_r25_resident_audio_service.py ^
  tests/test_saturn_midi_68k_r25_compile_probe.py ^
  tests/test_saturn_midi_68k_r25_compile_probe_cli.py
```

Then retain the ordinary full-suite checks:

```bat
python -m unittest discover -s tests -p "test_*.py"
python -m pytest -q
python -m pytest
```

## One-time legacy compiler matrix

The output directory must not already exist. This is an off-card, compile-only
operation:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_r25_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\SRK-Workspace\R25-MIDI-RR-COMPILE-GATE1"
```

Acceptance requires:

```text
RR variants              32
compiler return codes    all 0
object files             32 non-empty objects
image hashes             32 distinct hashes
RR selected              false
physical measurements    false
linker invoked           false
SCSP execution           false
MC68EC000 execution      false
SAROO writes             none
result                    SUCCESS
```

The evidence files are:

```text
R25-MIDI-RR-COMPILE-GATE1\SRK_MIDI_68K_R25_RR_COMPILE_MATRIX.json
R25-MIDI-RR-COMPILE-GATE1\SRK_MIDI_68K_R25_RR_COMPILE_MATRIX_LOG.txt
```

## Next gate

Only after the compiler matrix passes on Eridu should R25 create a fresh
standalone calibration build. That build must remain separate from R24, expose
the candidate RR value and release telemetry on screen, and require physical
duration measurements before producing a song candidate. No card deployment is
authorized by this compiler gate.
