# Saturn Audio — Sega Direct MIDI Link Gate

## Accepted compiler boundary

Eridu physically validated the Sega Direct MIDI compiler gate at repository
commit:

```text
c67f6d1f7363a6e0ed6b0912901677e00cd41169
```

Observed regression result:

```text
994 passed
34 subtests passed
```

Observed compiler result:

```text
Result : SUCCESS
Legacy SH-ELF GCC accepted the exact Sega SND_CtrlDirMidi adapter.
```

Accepted input fingerprints:

```text
SRK source:
364d7a5cd7c1023b797bedb0b97d763a65d2fd131e844c6ab4f032ca7c7b0ec4

SRK adapter header:
376cf81f0ffcfe246f084acf46b9d51ead1c57903781bbcdfda927e1843c037f

installed SEGA_SND.H:
17e74a4ead1f93f31997755d1a5f8bd6df80bf571d4f5201859d9141d07f9d7e

installed sega_snd.a:
7798cde921e65c3051ddcd0e242258350704f99ce64ba1167f27f2e09fb66407
```

The compiler gate proved the exact installed header contract. It deliberately
did not link the proprietary Sega library.

## Purpose of this gate

Advance exactly one production boundary:

```text
SRK Direct MIDI adapter object
        +
accepted installed sega_snd.a
        |
        v
relocatable SH link
        |
        v
symbol-table inspection
```

This is not a generic SDK survey.

The gate proves whether the installed Sega sound library actually satisfies the
adapter's `SND_CtrlDirMidi` reference and records every transitive undefined
symbol pulled in with that implementation.

## Why a relocatable link

The gate uses:

```text
-nostdlib
-m2
-Wl,-r
```

It therefore does not require a Saturn executable entry point, startup runtime,
ISO image, sound driver initialization, or hardware execution.

No broad `sega_sat.a` aggregate and no unrelated SBL library is silently added.

If `sega_snd.a` pulls additional dependencies, their exact undefined symbol
names become the next closure evidence.

## Acceptance

Full SUCCESS requires:

1. accepted source/header/library hashes unchanged;
2. exact Direct MIDI adapter compiles;
3. exact `sega_snd.a` relocatable link succeeds;
4. `SND_CtrlDirMidi` is no longer undefined;
5. the linked object contains no remaining undefined symbols;
6. PATH and inputs remain unchanged.

If item 4 passes but item 5 does not, the tool reports:

```text
DEPENDENCY CLOSURE REQUIRED
```

That is useful evidence, not a reason to guess libraries. The next tranche must
satisfy only the recorded transitive symbols.

## Safety boundary

The link gate performs no:

- executable image generation;
- ISO generation;
- Sega sound-driver initialization;
- Sound RAM write;
- SCSP write;
- MC68EC000 replacement;
- Saturn execution;
- SAROO/card write.

The R26-R28 synthetic renderer remains untouched.
