"""Post-validation of LLM-returned grounding offsets."""
from thefuzz import fuzz


def validate_and_fix_grounding(entity, chapter_text: str) -> tuple[str, float]:
    """Post-validate and fix offsets returned by LLM.

    Mutates entity.char_offset_start/end if correction needed.

    Returns: (alignment_status, confidence)
    - "exact" (1.0): extraction_text found at claimed offset
    - "fuzzy" (0.7): extraction_text found elsewhere, offsets corrected
    - "unaligned" (0.3): extraction_text not found in text at all
    """
    ext_text = entity.extraction_text.strip()

    # Check claimed offsets
    if entity.char_offset_start >= 0 and entity.char_offset_end > entity.char_offset_start:
        end = min(entity.char_offset_end, len(chapter_text))
        claimed = chapter_text[entity.char_offset_start:end].strip()
        if claimed == ext_text:
            return "exact", 1.0

    # Fuzzy fallback — find extraction_text anywhere in source
    idx = chapter_text.find(ext_text)
    if idx >= 0:
        entity.char_offset_start = idx
        entity.char_offset_end = idx + len(ext_text)
        return "fuzzy", 0.7

    # Partial match via thefuzz
    ratio = fuzz.partial_ratio(ext_text, chapter_text)
    if ratio > 80:
        return "fuzzy", 0.5

    return "unaligned", 0.3
