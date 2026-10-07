"""Offline manual additions for SAROO capture and SD-card exchange.

This module contains SRK product/domain documentation only. Rendering remains
owned by the Salix documentation framework/engine.
"""

from __future__ import annotations

from rikai_kotoba.application.help_content import GlossaryEntry
from salix.framework.documentation import (
    DocCallout,
    DocCalloutKind,
    DocCodeBlock,
    DocIconKind,
    DocIconLine,
    DocPage,
    DocParagraph,
    DocSection,
)


GLOSSARY: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        "Capture artifact",
        "An immutable SRK directory containing one or more captured memory-region files plus capture.json metadata. The manifest records addresses, sizes, checkpoint information, timestamps, and SHA-256 hashes so the capture can be verified later.",
        aliases=("capture",),
        related=("RAM dump", "checkpoint", "SHA-256", "provenance"),
    ),
    GlossaryEntry(
        "Checkpoint",
        "A human-readable name for the moment or game state when a memory capture was taken, such as title-screen, before-dialogue, or after-load. A useful checkpoint describes runtime context without hardcoding one game's addresses into SRK.",
        related=("capture artifact", "RAM dump", "provenance"),
    ),
    GlossaryEntry(
        "Cross-compiler",
        "A compiler that runs on one computer but produces machine code for another target processor. SAROO's Firm_Saturn build uses an SH-ELF cross-compiler on the development PC to create code for the Saturn's SuperH processor family.",
        aliases=("cross compiler",),
        related=("toolchain", "SaturnOrbit", "SAROO"),
    ),
    GlossaryEntry(
        "Makefile",
        "A text file describing how source files are compiled and linked into a program. The historical SAROO Firm_Saturn Makefile also used touch, cat, and rm; SRK-generated trees replace those file operations with srk_build_support.py while preserving the SH-ELF compile/link commands.",
        related=("toolchain", "cross-compiler"),
    ),
    GlossaryEntry(
        "SaturnOrbit",
        "A Sega Saturn development environment/tool distribution referenced by upstream SAROO for building Firm_Saturn. SRK can search a user-supplied SaturnOrbit or SH-ELF directory for the required build executables without modifying the system PATH.",
        related=("cross-compiler", "toolchain", "SAROO"),
    ),
    GlossaryEntry(
        "SD capture",
        "A workflow where Saturn-side code writes a requested memory range to a file on SAROO's SD card. SRK then imports that raw file on the PC into a verified capture artifact. This is useful before a live PC-to-SAROO transport exists.",
        aliases=("SD-card capture", "offline capture"),
        related=("SAROO", "capture artifact", "transport adapter"),
    ),
    GlossaryEntry(
        "SHA-256",
        "A cryptographic hash function SRK uses as an integrity fingerprint. If even one byte in a captured region changes, its SHA-256 value will almost certainly change, allowing capture verification to detect tampering or corruption.",
        aliases=("SHA256", "hash"),
        related=("capture artifact",),
    ),
    GlossaryEntry(
        "Toolchain",
        "The external programs needed to build generated SAROO Firm_Saturn source. SRK currently requires sh-elf-gcc, sh-elf-as, sh-elf-objdump, sh-elf-objcopy, and a Make-compatible driver; Python handles the historical touch, cat, and rm file operations inside the generated tree.",
        related=("cross-compiler", "Makefile", "SaturnOrbit"),
    ),
    GlossaryEntry(
        "Transport adapter",
        "A presentation-neutral implementation that obtains Saturn memory bytes for SRK. The capture coordinator only asks for address ranges; the adapter may later use SAROO firmware commands, SD-card exchange, serial communication, or another verified mechanism without changing capture storage or analysis.",
        related=("SAROO", "SD capture", "RAM dump"),
    ),
)


PAGES: dict[str, DocPage] = {
    "saroo-capture": DocPage(
        title="SAROO memory capture and SD-card exchange",
        lead="Capture runtime evidence from original Saturn hardware without inventing an unverified live transport protocol.",
        blocks=(
            DocCallout(
                title="Current development stage",
                body="SRK has a verified capture format, integrity checking, exact correlation tools, an upstream-compatible Saturn-side SD writer helper, and a read-only SH-ELF toolchain preflight. A stock/live PC-to-SAROO transport is not claimed yet. Until one is verified, SD-card exchange is the evidence-preserving bridge.",
                kind=DocCalloutKind.INFO,
                icon=DocIconKind.INFO,
            ),
        ),
        sections=(
            DocSection(
                "Why capture RAM?",
                (
                    DocParagraph(
                        "Static disc analysis can show that bytes exist in a file, but it cannot prove that the running program actually loaded, transformed, executed, or displayed those bytes. A RAM capture records what was present in the console at a known checkpoint so SRK can compare runtime state with disc content."
                    ),
                    DocIconLine(
                        "A useful evidence chain is disc -> file/offset -> loader or transform -> RAM address -> execution or display.",
                        DocIconKind.INFO,
                    ),
                ),
            ),
            DocSection(
                "The verified SAROO primitive",
                (
                    DocParagraph(
                        "Upstream SAROO's Saturn firmware exposes a write_file(name, offset, size, buffer) operation backed by its MCU file-write command. The upstream debug shell also demonstrates a 0x10000-byte (64 KiB) memory write. SRK therefore uses 64 KiB as the currently verified staging-write size instead of assuming that an entire 1 MiB Work RAM region is safe in one transfer."
                    ),
                    DocParagraph(
                        "SRK's helper creates or truncates the destination on the first chunk, then writes later chunks at explicit file offsets. A 1 MiB Work RAM dump therefore becomes sixteen 64 KiB writes."
                    ),
                ),
            ),
            DocSection(
                "Canonical Work RAM regions",
                (
                    DocCodeBlock(
                        "Work RAM-L  0x00200000 - 0x002FFFFF  1 MiB\n"
                        "Work RAM-H  0x06000000 - 0x060FFFFF  1 MiB",
                        language="text",
                    ),
                    DocParagraph(
                        "These are Saturn hardware regions, not game-specific constants. Future captures may request other caller-supplied ranges, but SRK does not embed commercial-title addresses in the reusable public layer."
                    ),
                ),
            ),
            DocSection(
                "Check the Firm_Saturn build toolchain",
                (
                    DocParagraph(
                        "The SRK-generated Firm_Saturn build requires five external build programs: sh-elf-gcc, sh-elf-as, sh-elf-objdump, sh-elf-objcopy, and a Make-compatible build driver. Physical inspection of SaturnOrbit R1 confirmed those tools are present in its SH_ELF tree."
                    ),
                    DocCodeBlock(
                        "srk-saroo-toolchain\n\n"
                        "srk-saroo-toolchain --toolchain-root C:\\path\\to\\SaturnOrbit",
                        language="bat",
                    ),
                    DocParagraph(
                        "The historical upstream Makefile also invokes touch, cat, and rm. SRK-generated trees replace those three file operations with srk_build_support.py, using the Python runtime SRK already requires. They are therefore not external preflight requirements."
                    ),
                    DocParagraph(
                        "The preflight is read-only. A supplied toolchain root is searched first, including historical SaturnOrbit SH_ELF and Other Utilities directories, then the existing process PATH is checked as a fallback. PATH is not modified by SRK. A READY discovery result means the five external build programs were found; only an actual Firm_Saturn build proves that the installation works correctly."
                    ),
                    DocParagraph(
                        "The pinned upstream tree also contains MAKE_ELF.bat, but that historical helper contains machine-specific absolute F: drive paths. SRK does not use that batch file as its portable build entry point. The build uses a separate generated source tree, a process-local toolchain environment, the upstream SH-ELF compiler commands, and SRK's portable file-operation helper."
                    ),
                    DocCallout(
                        title="No firmware deployment occurs here",
                        body="Toolchain preflight only discovers build programs. It does not compile, patch a known-good SAROO checkout, copy firmware to an SD card, or flash hardware.",
                        kind=DocCalloutKind.NOTE,
                        icon=DocIconKind.NOTE,
                    ),
                ),
            ),
            DocSection(
                "Import a raw SD dump",
                (
                    DocParagraph(
                        "After copying a raw capture file from the SAROO SD card to the PC, import it rather than treating the loose file as the final research record. Importing creates an immutable capture directory with address metadata and SHA-256 integrity information."
                    ),
                    DocCodeBlock(
                        "srk import-saroo-dump SRK_WRAMH.BIN ^\n"
                        "    --base-address 0x06000000 ^\n"
                        "    --expected-size 0x100000 ^\n"
                        "    --checkpoint title-screen ^\n"
                        "    --label work_ram_high",
                        language="bat",
                    ),
                    DocParagraph(
                        "By default the verified artifact is written beneath SRK-Workspace/Dumps/SAROO. The raw source dump is opened read-only and is not altered by the import."
                    ),
                ),
            ),
            DocSection(
                "Correlate a disc file with RAM",
                (
                    DocCodeBlock(
                        "srk correlate EXTRACTED.BIN 00_work_ram_high_06000000_00100000.bin ^\n"
                        "    --base-address 0x06000000",
                        language="bat",
                    ),
                    DocParagraph(
                        "The first correlation engine reports only exact byte-for-byte evidence. It suppresses highly repeated chunks and coalesces adjacent matches that preserve the same source-to-memory displacement. A missing exact match does not prove that the data is unused; it may have been decompressed, decoded, relocated, byte-swapped, or otherwise transformed."
                    ),
                ),
            ),
            DocSection(
                "What comes after SD exchange",
                (
                    DocParagraph(
                        "The capture coordinator is deliberately transport-neutral. When a verified live SAROO adapter is available, the GUI can request the same MemoryRange objects and receive the same CaptureArtifact results. The storage, hashing, correlation, and documentation layers do not need to be rewritten."
                    ),
                    DocCallout(
                        title="Do not confuse transport with evidence",
                        body="A faster or more convenient transport changes how bytes arrive at SRK; it does not change what must be recorded to make the result reproducible. Addresses, sizes, checkpoint context, hashes, and source provenance remain essential.",
                        kind=DocCalloutKind.NOTE,
                        icon=DocIconKind.NOTE,
                    ),
                ),
            ),
        ),
    ),
}


PAGE_ORDER: tuple[str, ...] = ("saroo-capture",)
