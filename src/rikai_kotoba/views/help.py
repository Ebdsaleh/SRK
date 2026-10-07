"""Offline Help & Glossary scene backed by the Salix documentation framework."""

from __future__ import annotations

import dearpygui.dearpygui as dpg

from rikai_kotoba.application import help_catalog as help_content
from salix.engine.documentation import DocumentationRenderer
from salix.framework.documentation import (
    DOCUMENTATION_SCALE_LABELS,
    documentation_scale_from_label,
    documentation_scale_label,
)
from salix.framework.responsive import LayoutCoordinator


class HelpView:
    """CHM-style offline manual with search, contents and an A-Z glossary."""

    def __init__(self, layout: LayoutCoordinator) -> None:
        self.layout = layout
        self.renderer: DocumentationRenderer | None = None
        self._built = False
        self._current_key = "welcome"
        self._watch_key = ("srk-help", id(self))

    def build(self, parent: str | int) -> None:
        if self._built:
            return
        self._built = True

        dpg.add_text("HELP & GLOSSARY", parent=parent, color=(105, 195, 255))
        dpg.add_text(
            "Offline manual: learn SRK, optical-disc terminology, Saturn research, and the workflow without requiring an Internet connection.",
            parent=parent,
            color=(185, 190, 200),
            wrap=1000,
        )
        dpg.add_spacer(height=6, parent=parent)

        with dpg.group(horizontal=True, parent=parent):
            dpg.add_input_text(
                tag="srk_help_search",
                hint="Search manual and glossary...",
                width=420,
                on_enter=True,
                callback=lambda *_args: self._search(),
            )
            dpg.add_button(label="Search", callback=lambda *_args: self._search())
            dpg.add_button(label="Home", callback=lambda *_args: self.open_page("welcome"))
            dpg.add_text("Documentation scale:")
            dpg.add_combo(
                tag="srk_help_scale",
                items=list(DOCUMENTATION_SCALE_LABELS.values()),
                default_value=documentation_scale_label(100),
                width=190,
                callback=lambda _s, value, _u: self._set_scale(value),
            )

        dpg.add_separator(parent=parent)

        with dpg.group(horizontal=True, parent=parent):
            with dpg.child_window(
                tag="srk_help_navigation",
                width=285,
                height=-1,
                border=True,
            ):
                with dpg.tab_bar():
                    with dpg.tab(label="Contents"):
                        self._build_contents()
                    with dpg.tab(label="Glossary A-Z"):
                        self._build_glossary_index()
                dpg.add_separator()
                dpg.add_text("Search results", color=(130, 190, 255))
                dpg.add_group(tag="srk_help_search_results")

            with dpg.child_window(
                tag="srk_help_document",
                width=-1,
                height=-1,
                border=False,
            ):
                pass

        self.renderer = DocumentationRenderer(
            "srk_help_document",
            layout=self.layout,
            scale_percent=100,
            on_link=self._open_target,
            tooltip=self._tooltip,
        )
        self.layout.watch_item(
            "srk_help_document",
            self._watch_key,
            lambda: self.renderer.reflow() if self.renderer is not None else None,
        )
        self.open_page("welcome")

    def _build_contents(self) -> None:
        labels = {
            "welcome": "Welcome / Start Here",
            "workspace": "Workspace and File Organization",
            "disc-images": "Disc Images and Filesystems",
            "mjolnir": "Mjölnir Utility",
            "saturn-saroo": "Saturn and SAROO",
            "saroo-capture": "SAROO Capture & SD Workflow",
            "provenance": "Runtime Provenance",
        }
        for key in help_content.PAGE_ORDER:
            dpg.add_button(
                label=labels.get(key, help_content.PAGES[key].title),
                width=-1,
                callback=self._page_button_clicked,
                user_data=key,
            )

    def _build_glossary_index(self) -> None:
        dpg.add_text(
            "Choose a letter, then select a term. Definitions are also used by contextual Help throughout SRK.",
            wrap=245,
            color=(170, 175, 185),
        )
        with dpg.group(horizontal=True):
            for letter in help_content.glossary_letters():
                dpg.add_button(
                    label=letter,
                    width=28,
                    callback=self._glossary_letter_clicked,
                    user_data=letter,
                )
        dpg.add_button(
            label="All terms",
            width=-1,
            callback=lambda *_args: self.open_glossary_letter(None),
        )

    def _tooltip(self, item: object, text: str) -> None:
        try:
            with dpg.tooltip(item):
                dpg.add_text(str(text), wrap=450)
        except Exception:
            pass

    def _set_scale(self, label: object) -> None:
        if self.renderer is not None:
            self.renderer.set_scale(documentation_scale_from_label(label))

    def _page_button_clicked(self, sender=None, app_data=None, user_data=None) -> None:
        """Open one Contents entry using Dear PyGui's explicit user-data channel."""

        del sender, app_data
        if user_data is not None:
            self.open_page(str(user_data))

    def _glossary_letter_clicked(self, sender=None, app_data=None, user_data=None) -> None:
        """Open one A-Z glossary bucket without relying on lambda argument capture."""

        del sender, app_data
        if user_data is not None:
            self.open_glossary_letter(str(user_data))

    def _search_result_clicked(self, sender=None, app_data=None, user_data=None) -> None:
        """Dispatch a search result target supplied through Dear PyGui user_data."""

        del sender, app_data
        if user_data is not None:
            self._open_search_result(str(user_data))

    def _open_target(self, target: str) -> None:
        if target.startswith("glossary:"):
            self.open_glossary_term(target.split(":", 1)[1])
            return
        self.open_page(target)

    def open_page(self, key: str) -> bool:
        document = help_content.page(key)
        if document is None or self.renderer is None:
            return False
        self._current_key = key
        self.renderer.render_page(document)
        return True

    def open_glossary_letter(self, letter: str | None) -> None:
        if self.renderer is None:
            return
        self._current_key = "glossary"
        self.renderer.render_page(help_content.glossary_page(letter))

    def open_glossary_term(self, term: str) -> bool:
        entry = help_content.glossary_entry(term)
        if entry is None or self.renderer is None:
            return False
        related = ""
        if entry.related:
            related = "Related terms: " + ", ".join(entry.related)
        from salix.framework.documentation import DocPage, DocParagraph, DocRole, DocSection

        blocks = [DocParagraph(entry.definition)]
        if related:
            blocks.append(DocParagraph(related, role=DocRole.MUTED))
        self._current_key = f"glossary:{entry.term}"
        self.renderer.render_page(
            DocPage(
                title=entry.term,
                lead="SRK Glossary",
                sections=(DocSection("Definition", tuple(blocks)),),
            )
        )
        return True

    def _search(self) -> None:
        query = str(dpg.get_value("srk_help_search") or "").strip()
        group = "srk_help_search_results"
        try:
            dpg.delete_item(group, children_only=True)
        except Exception:
            return

        results = help_content.search(query)
        if not query:
            dpg.add_text("Enter a word or phrase.", parent=group, wrap=245)
            return
        if not results:
            dpg.add_text("No matching manual pages or glossary terms.", parent=group, wrap=245)
            return

        for target, label in results[:40]:
            dpg.add_button(
                label=label,
                parent=group,
                width=-1,
                callback=self._search_result_clicked,
                user_data=target,
            )

    def _open_search_result(self, target: object) -> bool:
        if not isinstance(target, str):
            return False
        if target.startswith("page:"):
            return self.open_page(target.split(":", 1)[1])
        if target.startswith("glossary:"):
            return self.open_glossary_term(target.split(":", 1)[1])
        return False

    def on_show(self, **_kwargs) -> None:
        if self.renderer is not None:
            self.renderer.reflow(force=True)

    def update(self, _delta_seconds: float) -> None:
        return

    def dispose(self) -> None:
        self.layout.unwatch_item(self._watch_key)
