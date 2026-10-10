# Saturn Audio MIDI MC68EC000 Installer Contract

This tranche defines the bounded Sound-RAM installer for SRK's already-reviewed
protocol-only MC68EC000 MIDI consumer.

It is still a source-only, non-launching tranche.

The installer can copy and verify the 68K program image and reset vectors **only
while the sound CPU is already stopped**. Nothing in the current diagnostic
calls the installer.

## Reviewed program image

```text
program address  0x00000600
program end      0x000006A2 exclusive
program words    81
program bytes    162
stack value      0x0007FFF0
program SHA-256  2a0f30068be2815953569e2717af6c92197b08897fdca744607f5b4bee14e5c2
```

The program remains above the accepted dummy-loop/vector ownership and below the
MIDI mailbox at `0x00001000`.

## Reset vectors

The installer writes reset vectors using the same 16-bit Sound-RAM access
convention already used by the accepted standalone audio implementation:

```text
0x00000000  initial SSP = 0x0007FFF0
0x00000004  initial PC  = 0x00000600
```

32-bit values are written high word first, then low word.

The remaining exception vectors are not changed by this tranche. The currently
accepted standalone initialization already points them at the bounded dummy loop
at `0x00000400`.

## C API

```c
int srk_saturn_midi_68k_install_while_stopped(void);
int srk_saturn_midi_68k_verify_install(void);
```

`srk_saturn_midi_68k_install_while_stopped()`:

1. copies all 81 program words to Sound RAM at `0x00000600`;
2. writes the reset SSP vector;
3. writes the reset PC vector;
4. calls the read-back verifier;
5. returns non-zero only if the image and reset vectors match exactly.

The program bytes are written before reset vectors so the vectors never publish
the new entry point before the complete image exists.

`srk_saturn_midi_68k_verify_install()` reads back:

- reset SSP;
- reset PC;
- every program word.

It performs no launch action.

## SH-2 Sound-RAM aperture

The generated C uses only:

```text
0x25A00000  SH-2 Sound-RAM aperture
```

No SCSP register aperture is referenced.

## Explicit precondition

The installer is not responsible for stopping the MC68EC000.

Its API name and header comment deliberately state the precondition:

```text
MC68EC000 must already be stopped.
```

The future runtime orchestrator must use the already accepted SMPC command
sequencing to establish that condition before this function is ever called.
That orchestration is intentionally not part of this tranche.

## Safety boundary

This tranche does not:

- call the installer;
- stop or start the sound CPU;
- issue `SNDOFF`;
- issue `SNDON`;
- access SMPC COMREG/SF;
- access SCSP registers;
- publish the MIDI mailbox;
- select the new reset PC at runtime;
- execute the MC68EC000 program;
- create or deploy an R18 image;
- write SAROO.

The C implementation merely contains bounded Sound-RAM copy/read-back logic.
Because no production path calls it, no new runtime Sound-RAM write is enabled by
this source tranche.

## Ordering for the later launch tranche

After this source/compile/full-build path has been proven, a separate reviewed
runtime orchestrator can use the established hardware sequence:

```text
wait for safe SMPC command window
SNDOFF
    -> MC68EC000 stopped
install + verify 68K image/reset vectors
publish + verify deterministic MIDI mailbox/tone preload
SNDON
    -> first silent protocol-only 68K execution proof
```

The first execution proof must still perform **no MIDI SCSP note generation**.
Success is only the mailbox acknowledgement written by the protocol consumer.

Only after that physical proof is accepted should SRK add audible MIDI event
handling.

## Next gate

The immediate next step after this source gate is green is an isolated real
legacy SH-ELF compilation probe for:

```text
srk_saturn_midi_68k_installer.c
```

using the normal standalone C flags.

If accepted, link the installer into another fresh complete off-card standalone
image while it remains uncalled.

No card deployment is authorized by this document.
