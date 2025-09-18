"""Unified highlighting module for search results."""

from rich.text import Text


def highlight_text(text: str, patterns: list[str]) -> Text:
    """Apply highlighting to text for given patterns.

    Args:
        text: The text to highlight
        patterns: List of strings to highlight in the text

    Returns:
        Rich Text object with highlighted patterns
    """
    if not text or not patterns:
        return Text(text)

    rich_text = Text(text)
    text_lower = text.lower()

    # Track positions already highlighted to avoid overlaps
    highlighted_ranges: list[tuple[int, int]] = []

    # Highlight each pattern found (case-insensitive)
    for pattern in patterns:
        if not pattern:
            continue

        pattern_lower = pattern.lower()
        start = 0

        # Find all occurrences of the pattern
        while True:
            pos = text_lower.find(pattern_lower, start)
            if pos == -1:
                break

            end_pos = pos + len(pattern)

            # Check if this range overlaps with already highlighted ranges
            overlaps = False
            for existing_start, existing_end in highlighted_ranges:
                if pos < existing_end and end_pos > existing_start:
                    overlaps = True
                    break

            if not overlaps:
                # Apply consistent yellow background highlighting
                rich_text.stylize("bold black on yellow", pos, end_pos)
                highlighted_ranges.append((pos, end_pos))

            start = pos + 1

    return rich_text
