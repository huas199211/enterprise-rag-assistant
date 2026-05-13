import re


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    cleaned = re.sub(r"(?m)(?<!\n)(#{1,6}\s+)", r"\n\n\1", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []

    paragraphs = re.split(r"\n\s*\n", cleaned)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_text(para, chunk_size, overlap))
            continue
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current.strip():
                chunks.append(current.strip())
            current = "" if _is_heading(para) else _tail(current, overlap)
            if len(current) + len(para) + 2 > chunk_size:
                if current.strip():
                    chunks.append(current.strip())
                current = ""
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())
    return chunks


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _tail(text: str, overlap: int) -> str:
    if overlap <= 0:
        return ""
    return text[-overlap:].strip()


def _is_heading(text: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+", text.strip()))
