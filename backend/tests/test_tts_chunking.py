from app.generation.tts import split_for_tts


def test_split_for_tts_respects_paragraph_boundaries():
    paragraphs = [f"Paragraph number {i}. " + ("word " * 40) for i in range(6)]
    text = "\n\n".join(paragraphs)

    chunks = split_for_tts(text, target_chars=300)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) > 0


def test_split_for_tts_preserves_all_content():
    paragraphs = [f"Paragraph number {i}. " + ("word " * 40) for i in range(6)]
    text = "\n\n".join(paragraphs)

    chunks = split_for_tts(text, target_chars=300)

    original_words = text.split()
    reassembled_words = " ".join(chunks).split()
    assert reassembled_words == original_words


def test_split_for_tts_single_short_text_is_one_chunk():
    text = "Just one short paragraph."
    chunks = split_for_tts(text, target_chars=1000)
    assert chunks == [text]
