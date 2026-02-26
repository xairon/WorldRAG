"""Tests for structure-aware epub ingestion (V2)."""

from __future__ import annotations

from app.schemas.book import ParagraphType
from app.services.ingestion import _build_paragraphs_from_html, _classify_block_text


class TestClassifyBlockText:
    """Test HTML block classification into paragraph types."""

    def test_header_h1(self):
        assert _classify_block_text("h1", "Chapter Title") == ParagraphType.HEADER

    def test_header_h3(self):
        assert _classify_block_text("h3", "Section") == ParagraphType.HEADER

    def test_dialogue_guillemets(self):
        result = _classify_block_text("p", "\u00ab Bonjour ! \u00bb dit Jake.")
        assert result == ParagraphType.DIALOGUE

    def test_dialogue_tiret(self):
        result = _classify_block_text("p", "\u2014 Tu viens ?")
        assert result == ParagraphType.DIALOGUE

    def test_dialogue_dash(self):
        result = _classify_block_text("p", "\u2013 Non, r\u00e9pondit-elle.")
        assert result == ParagraphType.DIALOGUE

    def test_dialogue_smart_quotes(self):
        assert _classify_block_text("p", "\u201cHello,\u201d he said.") == ParagraphType.DIALOGUE

    def test_narration_default(self):
        result = _classify_block_text("p", "Jake observait la for\u00eat sombre.")
        assert result == ParagraphType.NARRATION

    def test_scene_break_stars(self):
        assert _classify_block_text("p", "***") == ParagraphType.SCENE_BREAK

    def test_scene_break_dashes(self):
        assert _classify_block_text("p", "---") == ParagraphType.SCENE_BREAK

    def test_scene_break_spaced_stars(self):
        assert _classify_block_text("p", "* * *") == ParagraphType.SCENE_BREAK

    def test_blue_box_skill(self):
        assert _classify_block_text("p", "[Skill Acquired: Shadowstep]") == ParagraphType.BLUE_BOX

    def test_blue_box_level(self):
        result = _classify_block_text("p", "[Level Up! You are now level 12]")
        assert result == ParagraphType.BLUE_BOX

    def test_blue_box_french(self):
        text = "[Comp\u00e9tence acquise : Pas de l'ombre]"
        assert _classify_block_text("p", text) == ParagraphType.BLUE_BOX


class TestBuildParagraphsFromHtml:
    """Test HTML to paragraph conversion."""

    def test_simple_paragraphs(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert len(paragraphs) == 2
        assert paragraphs[0].text == "First paragraph."
        assert paragraphs[0].type == ParagraphType.NARRATION
        assert paragraphs[0].index == 0
        assert paragraphs[1].index == 1

    def test_char_offsets_contiguous(self):
        html = "<p>First paragraph.</p><p>Second paragraph.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert paragraphs[0].char_start == 0
        assert paragraphs[0].char_end == len("First paragraph.")
        # +1 for \n separator
        assert paragraphs[1].char_start == paragraphs[0].char_end + 1

    def test_heading_detection(self):
        html = "<h1>Chapter One</h1><p>Text here.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert paragraphs[0].type == ParagraphType.HEADER
        assert paragraphs[1].type == ParagraphType.NARRATION

    def test_html_preserved(self):
        html = "<p><em>italic</em> and <strong>bold</strong></p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert "<em>" in paragraphs[0].html
        assert "<strong>" in paragraphs[0].html

    def test_empty_paragraphs_skipped(self):
        html = "<p>Text</p><p></p><p>More text</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert len(paragraphs) == 2

    def test_word_count_auto(self):
        html = "<p>One two three four five.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert paragraphs[0].word_count == 5

    def test_dialogue_paragraphs(self):
        html = "<p>\u00ab Salut ! \u00bb dit Jake.</p><p>Il sourit.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        assert paragraphs[0].type == ParagraphType.DIALOGUE
        assert paragraphs[1].type == ParagraphType.NARRATION

    def test_mixed_content(self):
        html = """
        <h2>Chapitre 1</h2>
        <p>Jake marchait dans la for\u00eat.</p>
        <p>\u00ab Qui va l\u00e0 ? \u00bb cria-t-il.</p>
        <p>***</p>
        <p>[Comp\u00e9tence acquise : Pas de l'ombre]</p>
        <p>Il continua son chemin.</p>
        """
        paragraphs = _build_paragraphs_from_html(html)
        types = [p.type for p in paragraphs]
        assert types == [
            ParagraphType.HEADER,
            ParagraphType.NARRATION,
            ParagraphType.DIALOGUE,
            ParagraphType.SCENE_BREAK,
            ParagraphType.BLUE_BOX,
            ParagraphType.NARRATION,
        ]

    def test_reconstructed_text_matches_offsets(self):
        """Verify that char offsets allow correct substring extraction."""
        html = "<p>First.</p><p>Second.</p><p>Third.</p>"
        paragraphs = _build_paragraphs_from_html(html)
        full_text = "\n".join(p.text for p in paragraphs)
        for p in paragraphs:
            assert full_text[p.char_start : p.char_end] == p.text
