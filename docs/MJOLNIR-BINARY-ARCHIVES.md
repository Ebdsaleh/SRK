# Mjolnir binary/archive inspection

Mjolnir's disc workflow understands CUE/BIN geometry and ISO-9660 filesystems.
The binary/archive inspection mode extends the same read-only research principle
to standalone binary containers such as static libraries.

The first supported archive container is the classic Unix `ar` format. The
inspector does not ask the compiler, linker, `ar`, `objdump`, or any other
external binary utility to identify the input. Python reads the source bytes
itself.

## Safety contract

Inspection is read-only:

- the source file is never modified;
- archive members are not extracted during the evidence pass;
- no compiler/linker/binutils process is executed;
- no output tree is created;
- no SDK library is copied into SRK;
- unknown member formats remain `unknown` instead of being guessed.

The report records source/member SHA-256 values, offsets, sizes, raw names,
byte-prefix evidence, and conservative format identification. ELF headers are
identified directly from their documented magic and header fields; other byte
signatures remain available for later analysis.

## Usage

Run the companion Mjolnir mode from the SRK virtual environment:

```bat
python -m rikai_kotoba.tools.mjolnir_binary "C:\path\to\library.a"
```

Multiple inputs can be inspected in one invocation so working and failing
libraries can be compared under identical logic:

```bat
python -m rikai_kotoba.tools.mjolnir_binary ^
  "C:\path\to\working.a" ^
  "C:\path\to\failing.a"
```

Use `--member-limit N` to bound console output for a very large archive.

## Stage 6B research use

For the current Saturn GFS/CDC link investigation, the intended evidence pass is
to inspect the installed SBL libraries directly, especially:

- `sega_gfs.a` — accepted by the current SH-ELF link backend;
- `SEGA_CDC.A` — currently rejected with `File format is ambiguous`;
- `SEGADGFS.A` — useful local comparison material.

The result should answer whether the libraries use the same archive wrapper and
whether their member byte signatures/object formats differ. Only after that
comparison should the standalone builder be changed.
