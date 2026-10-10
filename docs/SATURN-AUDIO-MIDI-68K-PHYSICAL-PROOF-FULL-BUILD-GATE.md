# Saturn Audio — MIDI 68K Physical-Proof Full-Build Gate

This gate proves that SRK's complete silent Saturn MIDI/MC68EC000 stack, including
the bounded physical-proof controller, survives the normal standalone Saturn
build before any production path is allowed to call it.

## Scope

The fresh derived project contains:

```text
generated MIDI event/tone data
+
SH-2 mailbox preload producer
+
protocol-only MC68EC000 program image
+
bounded MC68EC000 installer
+
adapter-neutral runtime orchestrator
+
real Saturn hardware adapter
+
bounded physical-proof controller
```

Everything is linked. The physical-proof controller remains **uncalled**.

## Baseline

The gate derives from a previously accepted successful standalone project. The
baseline tree is validated and never modified. The output directory must not
already exist.

The normal Python-native build orchestration is retained: Python invokes the
existing SH-ELF GCC/assembler/linker and `mkisofs.exe` directly and verifies the
resulting artifacts.

## Physical-proof controller

The linked controller is the reviewed one-shot seam:

```text
srk_saturn_midi_68k_physical_proof_begin()
  -> srk_saturn_midi_68k_protocol_begin()
     -> srk_saturn_midi_68k_hardware_adapter_ops()
```

and the later non-blocking poll path:

```text
srk_saturn_midi_68k_physical_proof_poll()
  -> srk_saturn_midi_68k_protocol_poll()
```

The controller itself contains no direct Saturn MMIO and no busy-wait loop.

## Required inert state

The derived manifest must record:

```text
midi_bridge_active                  false
midi_mailbox_producer_linked        true
midi_mailbox_producer_called        false
midi_68k_program_linked             true
midi_68k_program_installed          false
midi_68k_installer_linked           true
midi_68k_installer_called           false
midi_68k_runtime_linked             true
midi_68k_runtime_called             false
midi_68k_hardware_adapter_present   true
midi_68k_hardware_adapter_linked    true
midi_68k_hardware_adapter_called    false
midi_68k_physical_proof_linked      true
midi_68k_physical_proof_called      false
midi_68k_reset_vectors_changed      false
midi_sound_ram_writes               false
midi_scsp_mmio                      false
midi_smpc_commands                  false
midi_mc68ec000_execution            false
```

The proof-specific manifest section also records that the proof is linked but
not called and that the stack remains behaviorally inactive.

## Safety boundary

Although the linked source now contains the complete call chain that will later
reach real Saturn SMPC and Sound-RAM operations, no production control path
invokes the physical-proof controller in this gate.

Therefore this gate performs no runtime:

- `SNDOFF` or `SNDON` command;
- Sound-RAM write/read for the proof;
- reset-vector change;
- MC68EC000 installation or execution;
- SCSP MIDI voice access;
- SAROO/card write.

No R18 deployment is authorized by this gate.

## Source tests

Run:

```bat
python -m unittest discover -s tests -p "test_*.py"
python -m pytest -q
python -m pytest
```

After this tranche, expected totals are:

```text
unittest: 529 tests
pytest:   534 tests + 23 subtests
```

## Real off-card gate

Use a fresh output directory:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_physical_proof_full_build_gate ^
  --baseline-project "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-STAGE6B-GFS-GATE5" ^
  --output "C:\Users\Developer.ERIDU\Saturn-Dev\SRK-Diagnostics-R1-MIDI-68K-PHYSICAL-PROOF-INERT-FULL-GATE1"
```

Success requires the normal compile, startup assembly, mixed-format link, ISO,
packaged-PCM verification and MODE1/2352 packaging commands all to succeed.

Expected state summary:

```text
Producer linked       : YES
Producer called       : NO
68K image linked      : YES
68K installed         : NO
Installer linked      : YES
Installer called      : NO
Runtime linked        : YES
Runtime called        : NO
Hardware adapter      : YES
Adapter linked        : YES
Adapter called        : NO
Physical proof linked : YES
Physical proof called : NO
68K executed          : NO
Bridge active         : NO
Result                : SUCCESS
```

## Next gate

Only after this complete full-build gate succeeds may SRK add the explicit
standalone diagnostic control and on-screen telemetry that calls the bounded
physical proof.

The first physical Saturn execution remains silent/protocol-only. Acceptance is:

```text
READY          set
READ_SEQUENCE  1
READ_INDEX     1
LAST_ERROR     0
```

That proves the SH-2 -> Sound RAM -> MC68EC000 -> Sound RAM -> SH-2 round trip.
No MIDI-driven SCSP note should be attempted until that acknowledgement is
physically accepted.

After physical acknowledgement, continue expanding SRK's own MC68EC000
MIDI-file playback implementation before adding Sega Saturn native Sound API
compatibility.
