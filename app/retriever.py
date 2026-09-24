"""
Retrieval: the "R" in RAG.

Loads the knowledge base (one Markdown file per policy area), splits it into
small chunks (one policy line each, tagged with its section), and returns the
chunks most relevant to a question.

Ranking uses BM25, the standard keyword-relevance algorithm behind most search
engines. It needs no model download, which keeps the app light enough for
Docker and a small cloud container. The retriever is isolated in this file, so
it can be swapped for vector search later without touching the rest of the app.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

WORD = re.compile(r"[a-z0-9æøå%]+")
STOPWORDS = set("""a an the is are was be been to of in on at for by with from and or but if it its this that
i my me you your we our can do does how what when where which who why will would could should
there any some much many about into than then so not no yes please""".split())


def tokenize(text: str) -> list[str]:
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


@dataclass
class Chunk:
    source: str   # file name, e.g. "fees.md"
    section: str  # heading, e.g. "Fees"
    text: str     # one policy line

    def as_context(self) -> str:
        return f"[{self.source} | {self.section}] {self.text}"


class Retriever:
    def __init__(self, kb_dir: str):
        self.kb_dir = Path(kb_dir)
        self.chunks = self._load_chunks()
        if not self.chunks:
            raise ValueError(f"No documents found in {self.kb_dir}")
        # Section name is included in the indexed text so "fees" matches fee lines
        self.index = BM25Okapi([tokenize(f"{c.section} {c.text}") for c in self.chunks])

    def _load_chunks(self) -> list[Chunk]:
        chunks = []
        for path in sorted(self.kb_dir.glob("*.md")):
            section = path.stem
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#"):
                    section = line.lstrip("#").strip()
                elif line.startswith("- "):
                    chunks.append(Chunk(path.name, section, line[2:]))
        return chunks

    def search(self, question: str, k: int = 4) -> list[Chunk]:
        scores = self.index.get_scores(tokenize(question))
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in ranked[:k] if scores[i] > 0]
