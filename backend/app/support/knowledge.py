import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

WORDS = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "how",
    "i",
    "in",
    "is",
    "it",
    "my",
    "on",
    "the",
    "to",
    "with",
}


def tokenize(text: str) -> list[str]:
    tokens = []
    for word in WORDS.findall(text.lower()):
        if word.isascii():
            if word not in STOP_WORDS:
                tokens.append(word)
        else:
            tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


@dataclass(frozen=True)
class Passage:
    passage_id: str
    title: str
    path: str
    excerpt: str


class KnowledgeBase:
    def __init__(self, passages: list[Passage]):
        self.passages = tuple(passages)
        texts = [tokenize(f"{p.title}\n{p.excerpt}") for p in passages]
        self.frequencies = tuple(Counter(tokens) for tokens in texts)
        self.lengths = tuple(len(tokens) for tokens in texts)
        self.average_length = (sum(self.lengths) / len(texts) if texts else 0) or 1
        self.document_frequency = Counter(
            term for counts in self.frequencies for term in counts
        )

    @classmethod
    def from_directory(cls, directory: Path) -> KnowledgeBase:
        if not directory.is_dir():
            raise ValueError(f"Knowledge base directory does not exist: {directory}")
        passages = []
        for file in sorted(directory.glob("*.md")):
            title = file.stem
            index = 0
            for block in re.split(r"\n\s*\n", file.read_text(encoding="utf-8-sig")):
                block = block.strip()
                if not block:
                    continue
                if re.fullmatch(r"#{1,6} [^\n]+", block):
                    title = block.split(" ", 1)[1]
                    continue
                for start in range(0, len(block), 900):
                    excerpt = block[start : start + 900].strip()
                    if not excerpt:
                        continue
                    index += 1
                    passages.append(
                        Passage(f"{file.name}#{index}", title, file.name, excerpt)
                    )
        if not passages:
            raise ValueError(f"Knowledge base has no Markdown passages: {directory}")
        return cls(passages)

    def search(self, query: str, limit: int = 4) -> list[Passage]:
        terms = set(tokenize(query))
        ranked = []
        size = len(self.passages)
        for passage, counts, length in zip(
            self.passages, self.frequencies, self.lengths, strict=True
        ):
            matched = terms.intersection(counts)
            if len(matched) < 2:
                continue
            normalization = 1.2 * (0.25 + 0.75 * length / self.average_length)
            score = sum(
                math.log1p(
                    (size - self.document_frequency[term] + 0.5)
                    / (self.document_frequency[term] + 0.5)
                )
                * counts[term]
                * 2.2
                / (counts[term] + normalization)
                for term in sorted(matched)
            )
            ranked.append((score, passage))
        ranked.sort(key=lambda hit: (-hit[0], hit[1].passage_id))
        return [passage for _, passage in ranked[:limit]]
