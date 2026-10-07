"""Offline SRK manual and glossary content.

This module contains SRK domain knowledge only.  Presentation belongs to the
Salix documentation framework/engine, so the same material can later be used by
Dear PyGui, a headless/manual exporter, contextual tooltips, or another host.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from salix.framework.documentation import (
    DocCallout,
    DocCalloutKind,
    DocCodeBlock,
    DocIconKind,
    DocIconLine,
    DocLink,
    DocLinks,
    DocPage,
    DocParagraph,
    DocRole,
    DocSection,
)


@dataclass(frozen=True)
class GlossaryEntry:
    term: str
    definition: str
    aliases: tuple[str, ...] = ()
    related: tuple[str, ...] = ()


GLOSSARY: tuple[GlossaryEntry, ...] = (
    GlossaryEntry(
        "BIN",
        "A binary file containing raw or user-data sectors from an optical disc. A BIN file may represent one track or, depending on the dump format, more than one part of a disc. A matching CUE sheet is often needed to describe how the tracks should be interpreted.",
        aliases=("binary image",),
        related=("CUE", "sector", "track"),
    ),
    GlossaryEntry(
        "CUE",
        "A text-based cue sheet that describes an optical disc's track layout and names the files that contain those tracks. It can identify data tracks, audio tracks, indexes, and sector formats. Keep a CUE file together with every BIN file it references.",
        aliases=("cue sheet",),
        related=("BIN", "track", "sector"),
    ),
    GlossaryEntry(
        "Disc image",
        "A file or group of files that preserves the contents of an optical disc. Common forms include CUE/BIN and ISO. SRK treats original source images as read-only research inputs.",
        aliases=("image", "optical-disc image"),
        related=("CUE", "BIN", "ISO"),
    ),
    GlossaryEntry(
        "ISO",
        "A common disc-image form usually containing 2048-byte user-data sectors. An ISO file is not the same thing as the ISO-9660 filesystem, although ISO images commonly contain an ISO-9660 filesystem.",
        related=("ISO-9660", "sector", "disc image"),
    ),
    GlossaryEntry(
        "ISO-9660",
        "A filesystem standard used on CD-ROM media. It describes directories, filenames, file sizes, and the logical block addresses where file data is stored. SRK can walk this filesystem without changing the source image.",
        aliases=("ISO 9660",),
        related=("LBA", "disc image"),
    ),
    GlossaryEntry(
        "IP.BIN",
        "The Sega Saturn bootstrap/header area at the beginning of a Saturn disc's data track. It contains identification and boot metadata used when inspecting a Saturn title. In SRK this is read through the logical disc abstraction rather than by assuming one raw BIN layout.",
        aliases=("IP BIN",),
        related=("Saturn", "LBA"),
    ),
    GlossaryEntry(
        "LBA",
        "Logical Block Address. A sector number used to identify a position on a disc without referring to minute-second-frame notation. For example, LBA 16 means the seventeenth logical sector when counting from zero.",
        aliases=("logical block address",),
        related=("sector", "ISO-9660"),
    ),
    GlossaryEntry(
        "Mjölnir",
        "SRK's disc and hexadecimal inspection utility. It can discover supported images, list files, create hexadecimal views, and make structured extraction outputs while preserving the source image.",
        related=("hex dump", "source image"),
    ),
    GlossaryEntry(
        "Provenance",
        "Evidence describing where runtime data came from and how it arrived there. For SRK's Saturn research this can mean tracing a chain such as disc file -> file offset -> loader or transformation -> RAM address -> executed code or displayed data.",
        related=("RAM dump", "correlation"),
    ),
    GlossaryEntry(
        "RAM dump",
        "A captured copy of a region of the console's working memory. Comparing RAM dumps with disc files can reveal where data was loaded, relocated, decoded, decompressed, or transformed at runtime.",
        aliases=("memory dump",),
        related=("SAROO", "provenance", "correlation"),
    ),
    GlossaryEntry(
        "SAROO",
        "A Saturn cartridge/OD E platform that can run software and provides a useful development path for original-hardware research. SRK's planned SAROO tools will use it as a laboratory for memory capture and runtime experiments; final localization work should not require SAROO unless a project specifically chooses that dependency.",
        related=("Saturn", "RAM dump"),
    ),
    GlossaryEntry(
        "Saturn",
        "Sega's 32-bit game console released in the 1990s. It uses two SH-2 CPUs and a collection of specialized subsystems. SRK begins with Saturn support but keeps its reusable disc and localization layers platform-neutral where practical.",
        related=("SAROO", "IP.BIN"),
    ),
    GlossaryEntry(
        "Sector",
        "A fixed-size addressable unit on an optical disc. Different track formats can store different physical sector sizes; the user-data portion exposed to a filesystem may be smaller than the raw physical sector.",
        related=("LBA", "track", "CUE"),
    ),
    GlossaryEntry(
        "Source image",
        "The original disc image supplied to SRK for research. Source images are read-only by project policy. Extractions, patches, rebuilt images, hexadecimal dumps, and other generated artifacts must be written somewhere else.",
        related=("workspace", "disc image"),
    ),
    GlossaryEntry(
        "Track",
        "One continuous program area described by an optical disc layout. A track can contain computer data or CD audio. A multi-track Saturn disc may therefore have one data track followed by one or more audio tracks.",
        related=("CUE", "sector", "BIN"),
    ),
    GlossaryEntry(
        "Workspace",
        "A user-owned directory outside the source-code repository where SRK keeps game images, generated outputs, and hardware captures. Keeping these separate prevents research data and copyrighted media from being mixed into the public program source.",
        related=("source image", "RAM dump"),
    ),
    GlossaryEntry(
        "Correlation",
        "The process of comparing two data sources to find meaningful relationships. In SRK, a common example is searching a RAM capture for byte sequences or transformed structures originating from a file on disc.",
        related=("provenance", "RAM dump"),
    ),
    GlossaryEntry(
        "Hex dump",
        "A text representation of binary bytes using hexadecimal numbers, often accompanied by offsets and an ASCII view. Hexadecimal makes exact byte values easier to inspect, but a text hex dump is much larger than the original binary data.",
        aliases=("hexadecimal dump",),
        related=("Mjölnir",),
    ),
)


_GLOSSARY_BY_KEY = {
    key.casefold(): entry
    for entry in GLOSSARY
    for key in (entry.term, *entry.aliases)
}


def glossary_entry(term: str) -> GlossaryEntry | None:
    return _GLOSSARY_BY_KEY.get(str(term or "").strip().casefold())


def glossary_letters() -> tuple[str, ...]:
    return tuple(sorted({entry.term[0].upper() for entry in GLOSSARY if entry.term}))


def glossary_for_letter(letter: str) -> tuple[GlossaryEntry, ...]:
    prefix = str(letter or "").strip().upper()[:1]
    return tuple(
        sorted(
            (entry for entry in GLOSSARY if entry.term.upper().startswith(prefix)),
            key=lambda entry: entry.term.casefold(),
        )
    )


def contextual_help(term: str) -> str:
    entry = glossary_entry(term)
    if entry is None:
        return ""
    related = ""
    if entry.related:
        related = "\n\nRelated: " + ", ".join(entry.related)
    return f"{entry.term}\n\n{entry.definition}{related}"


PAGES: dict[str, DocPage] = {
    "welcome": DocPage(
        title="SRK Offline Manual",
        lead="A self-contained guide to disc research, localization workflows, Saturn terminology, and the tools built into SRK.",
        blocks=(
            DocCallout(
                title="Designed to work offline",
                body="This manual is part of the application. It should explain enough background that a new user can make useful progress without searching the Internet for every unfamiliar term.",
                kind=DocCalloutKind.INFO,
                icon=DocIconKind.INFO,
            ),
        ),
        sections=(
            DocSection(
                "Start here",
                (
                    DocParagraph(
                        "SRK is a retro-game localization and reverse-engineering toolkit. The first supported platform is the Sega Saturn. Its reusable layers understand optical-disc layouts, ISO-9660 filesystems, safe extraction, hexadecimal inspection, and application workflows without depending on one specific game."
                    ),
                    DocParagraph(
                        "If you are new to disc images, begin with Disc images and files. If you are preparing original-hardware research, read Saturn and SAROO after that. The Glossary is intended to be consulted whenever a technical term is unfamiliar."
                    ),
                    DocLinks(
                        "Recommended reading",
                        (
                            DocLink("Workspace", "workspace"),
                            DocLink("Disc images and files", "disc-images"),
                            DocLink("Saturn and SAROO", "saturn-saroo"),
                        ),
                    ),
                ),
            ),
            DocSection(
                "Safety rule",
                (
                    DocCallout(
                        title="Original media is read-only",
                        body="SRK must never modify your source disc image in place. Generated extracts, dumps, patched files, and rebuilt images belong in a separate output location. Keeping the original intact gives you a trustworthy reference for every experiment.",
                        kind=DocCalloutKind.WARNING,
                        icon=DocIconKind.WARNING,
                    ),
                ),
            ),
        ),
    ),
    "workspace": DocPage(
        title="Workspace and file organization",
        lead="Keep program source, original media, generated analysis, and hardware captures in clearly separated locations.",
        sections=(
            DocSection(
                "Recommended layout",
                (
                    DocCodeBlock(
                        "SRK-Workspace/\n"
                        "|-- Images/\n"
                        "|   `-- Saturn/\n"
                        "|-- Output/\n"
                        "`-- Dumps/\n"
                        "    `-- SAROO/",
                        language="text",
                    ),
                    DocParagraph(
                        "Images contains the original CUE/BIN or other supported disc sets. Output contains files created by SRK. Dumps contains runtime captures from real hardware. None of these directories need to live inside the Git/source-code repository."
                    ),
                ),
            ),
            DocSection(
                "CUE/BIN sets",
                (
                    DocParagraph(
                        "Keep a CUE file and every track file it references together. Renaming only one file can break the references stored inside the cue sheet. When copying a disc set into the workspace, copy the complete set first and verify it before deleting or moving any older copy."
                    ),
                ),
            ),
        ),
    ),
    "disc-images": DocPage(
        title="Disc images, tracks, sectors, and filesystems",
        lead="A disc image is not just a large folder. Several layers describe how physical sectors become logical files.",
        sections=(
            DocSection(
                "The layers",
                (
                    DocIconLine("A CUE sheet describes tracks and the files that store them.", DocIconKind.INFO),
                    DocIconLine("A track defines a continuous data or audio program area.", DocIconKind.INFO),
                    DocIconLine("Sectors are fixed-size addressable units inside a track.", DocIconKind.INFO),
                    DocIconLine("LBAs give sectors simple numeric addresses.", DocIconKind.INFO),
                    DocIconLine("ISO-9660 maps logical sectors into directories and files.", DocIconKind.INFO),
                ),
            ),
            DocSection(
                "Why the distinction matters",
                (
                    DocParagraph(
                        "A raw sector can contain headers, checksums, or other bytes in addition to the user-data payload. Audio tracks do not contain ISO filesystem payloads at all. SRK's logical disc abstraction keeps those differences below filesystem tools so higher-level code does not blindly assume that every sector is a 2352-byte data sector."
                    ),
                    DocCallout(
                        title="Audio is not an empty file",
                        body="If an ISO directory entry points into an audio track or otherwise cannot be read as user data, SRK reports that boundary instead of quietly manufacturing a zero-byte result.",
                        kind=DocCalloutKind.NOTE,
                        icon=DocIconKind.NOTE,
                    ),
                ),
            ),
        ),
    ),
    "saturn-saroo": DocPage(
        title="Sega Saturn and SAROO research",
        lead="SRK uses disc analysis on the PC and runtime evidence from original hardware as complementary tools.",
        sections=(
            DocSection(
                "Saturn disc inspection",
                (
                    DocParagraph(
                        "Saturn support begins with the disc's bootstrap/header information and ISO-9660 filesystem. These identify what is on the disc, but they do not prove what bytes a running game actually executes or displays."
                    ),
                ),
            ),
            DocSection(
                "SAROO as a laboratory",
                (
                    DocParagraph(
                        "The planned SAROO layer will support controlled original-hardware experiments such as capturing RAM regions and applying explicitly requested runtime probes. The purpose is to replace guesswork with evidence."
                    ),
                    DocParagraph(
                        "A useful provenance chain is: disc -> file/LBA/offset -> loader or transform -> RAM -> execution or display. Once that path is known, localization work can target the real runtime data instead of repeatedly patching plausible-looking bytes and hoping the game reads them."
                    ),
                ),
            ),
        ),
    ),
    "mjolnir": DocPage(
        title="Mjölnir disc and hexadecimal utility",
        lead="Mjölnir is SRK's inspection utility for discovering disc images, listing files, producing hexadecimal views, and creating structured outputs.",
        sections=(
            DocSection(
                "Typical use",
                (
                    DocCodeBlock(
                        'srk-mjolnir "C:\\Users\\Developer.ERIDU\\SRK-Workspace\\Images\\Saturn" '
                        '--output-dir "C:\\Users\\Developer.ERIDU\\SRK-Workspace\\Output"',
                        language="bat",
                    ),
                    DocParagraph(
                        "Supplying explicit input and output locations keeps generated files out of the source repository. If an output name already exists, Mjölnir provides controlled conflict handling rather than silently overwriting it."
                    ),
                ),
            ),
        ),
    ),
    "provenance": DocPage(
        title="Runtime provenance and correlation",
        lead="Finding matching bytes is useful; proving where runtime data came from is more useful.",
        sections=(
            DocSection(
                "Correlation",
                (
                    DocParagraph(
                        "A correlation search compares a disc file with a RAM capture and reports candidate relationships. An exact byte match is the simplest case. More difficult cases may involve relocation, decompression, byte swapping, decoding, or a game-specific runtime structure."
                    ),
                ),
            ),
            DocSection(
                "Provenance",
                (
                    DocParagraph(
                        "Provenance records the evidence around a candidate: which source file and offset were involved, where the data appeared in memory, what transformation was observed, and what runtime event made the relationship visible. This evidence is what turns a lucky patch into a reproducible reverse-engineering result."
                    ),
                ),
            ),
        ),
    ),
}


PAGE_ORDER: tuple[str, ...] = (
    "welcome",
    "workspace",
    "disc-images",
    "mjolnir",
    "saturn-saroo",
    "provenance",
)


def page(key: str) -> DocPage | None:
    return PAGES.get(str(key or "").strip())


def search(query: str) -> tuple[tuple[str, str], ...]:
    """Search manual pages and glossary entries without requiring a backend."""

    needle = str(query or "").strip().casefold()
    if not needle:
        return ()

    results: list[tuple[str, str]] = []
    for key in PAGE_ORDER:
        document = PAGES[key]
        fragments = [document.title, document.lead]
        fragments.extend(
            block.text
            for block in document.blocks
            if isinstance(block, DocParagraph)
        )
        for section in document.sections:
            fragments.append(section.title)
            for block in section.blocks:
                if isinstance(block, DocParagraph):
                    fragments.append(block.text)
                elif isinstance(block, DocCallout):
                    fragments.extend((block.title, block.body))
                elif isinstance(block, DocIconLine):
                    fragments.append(block.text)
                elif isinstance(block, DocCodeBlock):
                    fragments.extend((block.caption, block.text))
        if needle in "\n".join(fragments).casefold():
            results.append((f"page:{key}", document.title))

    for entry in GLOSSARY:
        haystack = "\n".join(
            (entry.term, entry.definition, *entry.aliases, *entry.related)
        ).casefold()
        if needle in haystack:
            results.append((f"glossary:{entry.term}", entry.term))

    return tuple(results)


def glossary_page(letter: str | None = None) -> DocPage:
    entries: Iterable[GlossaryEntry]
    title = "Glossary A-Z"
    if letter:
        entries = glossary_for_letter(letter)
        title = f"Glossary — {str(letter).strip().upper()[:1]}"
    else:
        entries = sorted(GLOSSARY, key=lambda entry: entry.term.casefold())

    sections = tuple(
        DocSection(
            entry.term,
            (
                DocParagraph(entry.definition),
                *(
                    (DocParagraph("Related: " + ", ".join(entry.related), role=DocRole.MUTED),)
                    if entry.related
                    else ()
                ),
            ),
        )
        for entry in entries
    )
    return DocPage(
        title=title,
        lead="Technical terms used by SRK, explained without assuming prior reverse-engineering experience.",
        sections=sections,
    )
