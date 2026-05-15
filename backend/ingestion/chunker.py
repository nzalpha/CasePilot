from typing import TypedDict


class TextPage(TypedDict):
    page_number: int
    text: str


class Chunk(TypedDict):
    chunk_id: str
    text: str
    page_number: int
    position: int


WORDS_PER_TOKEN = 0.75


def token_limit_to_word_count(token_limit: int) -> int:
    return max(1, int(token_limit * WORDS_PER_TOKEN))


def approximate_token_count(text: str) -> int:
    words = len(text.split())
    return int(words / WORDS_PER_TOKEN) if words else 0


def chunk_pages(
    pages: list[TextPage],
    document_id: str,
    max_tokens: int = 512,
    overlap_tokens: int = 64,
) -> list[Chunk]:
    max_words = token_limit_to_word_count(max_tokens)
    overlap_words = token_limit_to_word_count(overlap_tokens)
    if overlap_words >= max_words:
        raise ValueError("overlap_tokens must be smaller than max_tokens")

    chunks: list[Chunk] = []
    position = 0

    for page in pages:
        words = page["text"].split()
        if not words:
            continue

        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunk_words = words[start:end]
            chunks.append(
                {
                    "chunk_id": f"{document_id}_chunk_{position}",
                    "text": " ".join(chunk_words),
                    "page_number": page["page_number"],
                    "position": position,
                }
            )
            position += 1

            if end == len(words):
                break
            start = end - overlap_words

    return chunks
