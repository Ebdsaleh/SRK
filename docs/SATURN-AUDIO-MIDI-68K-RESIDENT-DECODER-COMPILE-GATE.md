# Saturn Audio — General Resident MIDI 68K Decoder Compile Gate

## Purpose

This gate is the second lock on the post-R19 Phase-A general resident decoder.

The source regression suite validates the actual generated MC68000 words with a
reviewed-subset host interpreter.  This compiler gate separately proves that the
same generated image can be represented as C89 constant data accepted by the
real legacy SH-ELF GCC toolchain used by SRK's standalone Saturn build.

It does not install or execute the MC68EC000 program.

## Pinned image

The reviewed Phase-A image is content-independent and is locked to:

```text
program address : 0x00004000
word count      : 239
byte size       : 478
program end     : 0x000041DE
runtime records : 1..32
embedded records: none
SHA-256         : d915d0222a482f19fa7dca1c5996a45684c410c6467bc88957c9a4c41b2f74d4
```

Any machine-word change requires the image-lock test and this gate to be
reviewed again.

## Generated compile inputs

The probe writes only into a caller-supplied fresh off-card directory:

```text
srk_saturn_midi_68k_resident_decoder.c
srk_saturn_midi_68k_resident_decoder.h
srk_saturn_midi_68k_resident_decoder.o
SRK_MIDI_68K_RESIDENT_DECODER_COMPILE_PROBE_LOG.txt
SRK_MIDI_68K_RESIDENT_DECODER_COMPILE_PROBE.json
```

The source/header are generated from the pinned Python image builder.  Their
hashes are taken before compilation and checked again afterwards.

## Compiler policy

The probe resolves `sh-elf-gcc` from the supplied Saturn development root and
uses the same C policy as the standalone project:

```text
-Wall
-Werror
-m2
-O0
-ffreestanding
-fno-builtin
```

The action is compile-only (`-c`).

## Safety policy

The report must record:

```text
python_native_orchestration = true
shell_used                  = false
path_mutated                = false
generated_inputs_unchanged  = true
linker_invoked              = false
iso_builder_invoked         = false
sd_writes                   = false
sound_ram_writes            = false
scsp_mmio                    = false
smpc_commands                = false
mc68ec000_program_installed  = false
mc68ec000_execution          = false
```

The output path must not already exist.  The probe refuses to merge or
overwrite prior evidence.

## Real compiler command

After the source suite is green, run:

```bat
python -m rikai_kotoba.tools.saturn_midi_68k_resident_decoder_compile_probe ^
  --saturn-root "C:\Users\Developer.ERIDU\Saturn-Dev" ^
  --output "C:\Users\Developer.ERIDU\SRK-Workspace\MIDI-68K-RESIDENT-DECODER-COMPILE-GATE1"
```

The output directory must be fresh.

A successful result proves only that the legacy compiler accepted the generated
constant representation.  It does not prove the new MC68000 instructions on
hardware.

## Next gate

Only after source tests and this compile probe pass should SRK derive a fresh
standalone image with the decoder **linked but still uninstalled/unexecuted**.
That full-build gate will preserve R19 and remain off-card.

> Safer is secure, secure is faster.
