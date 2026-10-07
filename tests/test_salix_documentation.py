from __future__ import annotations

import unittest

from salix.framework.documentation import (
    DEFAULT_DOCUMENTATION_SCALE,
    DocCallout,
    DocCalloutKind,
    DocLayout,
    DocPage,
    DocParagraph,
    DocRole,
    DocSection,
    DocumentationLayoutTheme,
    documentation_bounds,
    documentation_scale_from_label,
    documentation_scale_label,
    normalise_documentation_scale,
    resolve_documentation_layout,
    role_font_size,
)
from salix.framework.geometry import HorizontalAlign


class SalixDocumentationTests(unittest.TestCase):
    def test_semantic_page_is_backend_neutral_data(self):
        page = DocPage(
            title="Offline Manual",
            lead="Everything needed to begin without Internet access.",
            sections=(
                DocSection(
                    "Getting started",
                    (
                        DocParagraph("Open a workspace."),
                        DocCallout(
                            "Source images are read-only.",
                            kind=DocCalloutKind.WARNING,
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(page.title, "Offline Manual")
        self.assertEqual(page.sections[0].blocks[0].role, DocRole.BODY)

    def test_documentation_layout_preserves_configuration_and_constrains_runtime(self):
        resolved = resolve_documentation_layout(
            theme=DocumentationLayoutTheme(maximum_width=1200),
            override=DocLayout(
                minimum_width=500,
                document_alignment=HorizontalAlign.CENTER,
            ),
        )
        self.assertEqual(resolved.maximum_width, 1200)
        bounds = documentation_bounds(700, 500, layout=resolved)
        self.assertLessEqual(bounds.document.width, 700)
        self.assertGreater(bounds.content.width, 0)

    def test_invalid_override_falls_back_without_poisoning_other_fields(self):
        resolved = resolve_documentation_layout(
            override=DocLayout(minimum_width=-1, padding_left=40)
        )
        self.assertEqual(resolved.minimum_width, 420)
        self.assertEqual(resolved.padding_left, 40)
        self.assertTrue(
            any(name == "minimum_width" for name, _rejection in resolved.rejected)
        )

    def test_documentation_scale_normalisation_and_labels(self):
        self.assertEqual(normalise_documentation_scale(112), 115)
        self.assertEqual(documentation_scale_from_label("115% - Large"), 115)
        self.assertEqual(documentation_scale_label(DEFAULT_DOCUMENTATION_SCALE), "100% - Comfortable")

    def test_role_font_sizes_are_semantic_and_bounded(self):
        body = role_font_size(DocRole.BODY, 15, 100)
        title = role_font_size(DocRole.PAGE_TITLE, 15, 100)
        self.assertGreater(title, body)
        self.assertLessEqual(role_font_size(DocRole.PAGE_TITLE, 100, 130), 36)

    def test_documentation_renderer_module_imports_headlessly(self):
        from salix.engine.documentation import DocumentationMediaCache, DocumentationRenderer

        self.assertTrue(callable(DocumentationRenderer))
        self.assertTrue(callable(DocumentationMediaCache))


if __name__ == "__main__":
    unittest.main()
