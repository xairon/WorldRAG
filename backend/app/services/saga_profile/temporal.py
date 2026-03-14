"""NarrativeTemporalMapper — maps (book, chapter, scene_order) ↔ datetime.

Provides a stable, reversible encoding of narrative positions into datetime
values for use with Graphiti's bi-temporal model.
"""

from datetime import datetime, timedelta, timezone


class NarrativeTemporalMapper:
    """Maps narrative positions to/from datetime for Graphiti bi-temporal storage.

    Encoding:
        dt = EPOCH + timedelta(days=(book_num - 1) * BOOK_OFFSET_DAYS + chapter_num,
                               seconds=scene_order)

    This gives each book a 10,000-day (~27-year) window, each chapter a 1-day
    slot within that window, and each scene a per-second slot within the day.
    """

    EPOCH: datetime = datetime(2000, 1, 1)
    BOOK_OFFSET_DAYS: int = 10_000  # ~27 years per book

    @staticmethod
    def to_datetime(book_num: int, chapter_num: int, scene_order: int = 0) -> datetime:
        """Convert a narrative position to a datetime.

        Args:
            book_num: 1-based book number (must be >= 1).
            chapter_num: 0-based chapter number (must be >= 0).
            scene_order: Scene position within the chapter in seconds (>= 0).

        Returns:
            A naive datetime encoding the narrative position.

        Raises:
            ValueError: If book_num < 1 or chapter_num < 0 or scene_order < 0.
        """
        if book_num < 1:
            raise ValueError(f"book_num must be >= 1, got {book_num!r}")
        if chapter_num < 0:
            raise ValueError(f"chapter_num must be >= 0, got {chapter_num!r}")
        if scene_order < 0:
            raise ValueError(f"scene_order must be >= 0, got {scene_order!r}")

        days = (book_num - 1) * NarrativeTemporalMapper.BOOK_OFFSET_DAYS + chapter_num
        return NarrativeTemporalMapper.EPOCH + timedelta(days=days, seconds=scene_order)

    @staticmethod
    def from_datetime(dt: datetime) -> tuple[int, int, int]:
        """Recover the narrative position from a datetime.

        Args:
            dt: A naive datetime previously produced by to_datetime.

        Returns:
            A (book_num, chapter_num, scene_order) tuple.

        Raises:
            ValueError: If dt is before EPOCH.
        """
        epoch = NarrativeTemporalMapper.EPOCH
        if dt < epoch:
            raise ValueError(
                f"dt must be >= EPOCH ({epoch.isoformat()}), got {dt.isoformat()!r}"
            )

        delta = dt - epoch
        total_seconds = int(delta.total_seconds())
        total_days = total_seconds // 86_400
        scene_order = total_seconds % 86_400

        book_num = total_days // NarrativeTemporalMapper.BOOK_OFFSET_DAYS + 1
        chapter_num = total_days % NarrativeTemporalMapper.BOOK_OFFSET_DAYS

        return (book_num, chapter_num, scene_order)
