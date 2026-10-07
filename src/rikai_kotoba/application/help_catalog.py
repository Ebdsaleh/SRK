"""Composed offline Help/Glossary catalog for SRK.

Keeping major product areas in separate content modules prevents the manual from
becoming one giant source file while preserving one searchable catalog for the
Dear PyGui Help scene and future documentation exporters.
"""

from __future__ import annotations

from typing import Iterable

from rikai_kotoba.application import help_content as base
from rikai_kotoba.application import saroo_help_content as saroo
from rikai_kotoba.application.help_content import GlossaryEntry
from salix.framework.documentation import (
    DocCallout,
    DocCodeBlock,
    DocIconLine,
    DocPage,
    DocParagraph,
    DocRole,
    DocSection,
)


PAGE_ORDER: tuple[str, ...] = (*base.PAGE_ORDER, *saroo.PAGE_ORDER)
PAGES: dict[str, DocPage] = {**base.PAGES, **saroo.PAGES}
GLOSSARY: tuple[GlossaryEntry, ...] = (*base.GLOSSARY, *saroo.GLOSSARY)


def _glossary_index() -> dict[str, GlossaryEntry]:
    index: dict[str, GlossaryEntry] = {}
    for entry in GLOSSARY:
        for key in (entry.term, *entry.aliases):
            folded = str(key).casefold()
            if folded in index:
                raise ValueError(f"duplicate glossary key: {key}")
            index[folded] = entry
    return index


_GLOSSARY_BY_KEY = _glossary_index()


def page(key: str) -> DocPage | None:
    return PAGES.get(str(key or "").strip())


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


def _page_search_text(document: DocPage) -> str:
    fragments: list[str] = [document.title, document.lead]
    for block in document.blocks:
        if isinstance(block, DocParagraph):
            fragments.append(block.text)
        elif isinstance(block, DocCallout):
            fragments.extend((block.title, block.body))
        elif isinstance(block, DocIconLine):
            fragments.append(block.text)
        elif isinstance(block, DocCodeBlock):
            fragments.extend((block.caption, block.text))
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
    return "\n".join(fragments)


def search(query: str) -> tuple[tuple[str, str], ...]:
    """Search every composed manual page and glossary entry."""

    needle = str(query or "").strip().casefold()
    if not needle:
        return ()

    results: list[tuple[str, str]] = []
    for key in PAGE_ORDER:
        document = PAGES[key]
        if needle in _page_search_text(document).casefold():
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
                    (
                        DocParagraph(
                            "Related: " + ", ".join(entry.related),
                            role=DocRole.MUTED,
                        ),
                    )
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
