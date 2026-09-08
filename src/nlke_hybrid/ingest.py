from __future__ import annotations

import ast
import fnmatch
import hashlib
import re
from pathlib import Path
from typing import Iterable

from .config import HybridConfig, is_secret_path
from .models import Chunk

TEXT_SUFFIXES = {".md", ".markdown", ".py", ".rst", ".txt"}
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _bounded(text: str, start: int, end: int, target: int, overlap: int) -> Iterable[tuple[str, int, int]]:
    words = _tokens(text)
    if not words:
        return
    cursor = 0
    while cursor < len(words):
        chunk_words = words[cursor : cursor + target]
        if not chunk_words:
            break
        yield " ".join(chunk_words), start, end
        if cursor + target >= len(words):
            break
        cursor += max(1, target - overlap)


def _markdown_chunks(text: str, target: int, overlap: int) -> Iterable[tuple[str, str, int, int, str | None]]:
    lines = text.splitlines()
    sections: list[tuple[str, int, list[str]]] = []
    title = "document"
    start = 1
    body: list[str] = []
    for number, line in enumerate(lines, 1):
        match = HEADING.match(line)
        if match:
            if body:
                sections.append((title, start, body))
            title, start, body = match.group(2), number, [line]
        else:
            body.append(line)
    if body:
        sections.append((title, start, body))
    for title, section_start, section_lines in sections:
        section_end = section_start + len(section_lines) - 1
        for block, begin, end in _bounded("\n".join(section_lines), section_start, section_end, target, overlap):
            yield block, title, begin, end, None


def _python_chunks(text: str, target: int, overlap: int) -> Iterable[tuple[str, str, int, int, str | None]]:
    lines = text.splitlines()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        yield from _paragraph_chunks(text, target, overlap)
        return
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    covered: set[int] = set()
    for node in nodes:
        start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
        covered.update(range(start, end + 1))
        part = "\n".join(lines[start - 1 : end])
        for block, _, _ in _bounded(part, start, end, target, overlap):
            yield block, node.name, start, end, node.name
    remainder = "\n".join(line for index, line in enumerate(lines, 1) if index not in covered).strip()
    if remainder:
        for block, _, _ in _bounded(remainder, 1, len(lines), target, overlap):
            yield block, "module", 1, len(lines), None


def _paragraph_chunks(text: str, target: int, overlap: int) -> Iterable[tuple[str, str, int, int, str | None]]:
    lines = text.splitlines()
    paragraphs = re.split(r"\n\s*\n", text)
    cursor = 1
    for paragraph in paragraphs:
        height = max(1, paragraph.count("\n") + 1)
        for block, start, end in _bounded(paragraph, cursor, cursor + height - 1, target, overlap):
            yield block, "text", start, end, None
        cursor += height + 1


def iter_source_files(config: HybridConfig) -> Iterable[tuple[dict, Path, str]]:
    for source in config.raw["sources"]:
        root = config.source_path(source)
        candidates = [root] if root.is_file() else sorted({path for pattern in source["include"] for path in root.glob(pattern)})
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or is_secret_path(path):
                continue
            relative = path.name if root.is_file() else path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(relative, pattern) or Path(relative).match(pattern) for pattern in source["exclude"]):
                continue
            yield source, path, relative


def scan_chunks(config: HybridConfig) -> list[Chunk]:
    retrieval = config.raw["retrieval"]
    target, overlap = int(retrieval["chunk_tokens"]), int(retrieval["chunk_overlap_tokens"])
    out: list[Chunk] = []
    for source, path, relative in iter_source_files(config):
        text = path.read_text(encoding="utf-8", errors="replace")
        document_id = f"{source['id']}:{relative}"
        if path.suffix.lower() in {".md", ".markdown"}:
            raw_chunks = _markdown_chunks(text, target, overlap)
        elif path.suffix.lower() == ".py":
            raw_chunks = _python_chunks(text, target, overlap)
        else:
            raw_chunks = _paragraph_chunks(text, target, overlap)
        for ordinal, (body, title, line_start, line_end, symbol) in enumerate(raw_chunks):
            digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
            ident = hashlib.sha256(f"{document_id}:{ordinal}:{digest}".encode()).hexdigest()
            out.append(Chunk(
                id=f"chunk:{ident}", document_id=document_id, source_id=source["id"], path=relative,
                ordinal=ordinal, content_hash="sha256:" + digest, text=body, title=title, symbol=symbol,
                line_start=line_start, line_end=line_end, token_count=len(_tokens(body)),
                cloud_eligible=bool(source["cloud_eligible"]),
            ))
    return out
