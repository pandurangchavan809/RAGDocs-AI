import re

from PyPDF2 import PdfReader


def allowed_file(filename):
    return "." in filename and filename.lower().endswith(".pdf")


def normalize_pdf_text(text):
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    paragraphs = []
    current = []

    for line in raw_lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue

        current.append(line)
        if line.endswith((".", "!", "?", ":", ";")) and len(" ".join(current)) >= 120:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    cleaned_paragraphs = [
        paragraph for paragraph in paragraphs if is_meaningful_text(paragraph, 10)
    ]
    return "\n\n".join(cleaned_paragraphs).strip()


def is_meaningful_text(text, min_words=18):
    words = re.findall(r"[A-Za-z]{2,}", text)
    if len(words) < min_words:
        return False

    letters = sum(char.isalpha() for char in text)
    total = max(len(text), 1)
    return letters / total >= 0.45


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def extract_pdf_pages(file_path):
    reader = PdfReader(str(file_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        cleaned_text = normalize_pdf_text(page.extract_text() or "")
        if cleaned_text:
            pages.append({"page_number": page_number, "text": cleaned_text})

    return pages


def split_text(pages):
    max_chunk_chars = 1050
    overlap_sentences = 1
    chunks = []

    for page in pages:
        paragraphs = [part.strip() for part in page["text"].split("\n\n") if part.strip()]
        current_sentences = []
        current_length = 0

        for paragraph in paragraphs:
            sentences = split_sentences(paragraph) or [paragraph]
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                sentence_length = len(sentence) + 1
                if current_sentences and current_length + sentence_length > max_chunk_chars:
                    chunk_text = " ".join(current_sentences).strip()
                    if is_meaningful_text(chunk_text):
                        chunks.append(
                            {
                                "page_number": page["page_number"],
                                "text": chunk_text,
                            }
                        )
                    current_sentences = current_sentences[-overlap_sentences:]
                    current_length = sum(len(item) + 1 for item in current_sentences)

                current_sentences.append(sentence)
                current_length += sentence_length

        if current_sentences:
            chunk_text = " ".join(current_sentences).strip()
            if is_meaningful_text(chunk_text):
                chunks.append(
                    {
                        "page_number": page["page_number"],
                        "text": chunk_text,
                    }
                )

    return chunks
