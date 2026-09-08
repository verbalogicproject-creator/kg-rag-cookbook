from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .errors import NLKEError
from .evaluation import evaluate
from .pipeline import HybridPipeline


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nlke-hybrid", description="Declared local-cloud hybrid KG-RAG")
    parser.add_argument("--config", default="hybrid-rag.json", help="path to hybrid-rag.json")
    parser.add_argument("--json", action="store_true", help="emit structured JSON (the default output is also JSON)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    index = commands.add_parser("index")
    index.add_argument("--providers", choices=("local", "cloud", "both"), default="local")
    commands.add_parser("status")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--mode", choices=("lexical", "local", "cloud", "both"))
    search.add_argument("--no-rerank", action="store_true")
    search.add_argument("--no-graph", action="store_true")
    ask = commands.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--mode", choices=("local", "cloud", "both"))
    evaluation = commands.add_parser("evaluate")
    evaluation.add_argument("queries")
    evaluation.add_argument("--modes", nargs="+", choices=("lexical", "local", "cloud", "both"), default=("lexical", "local", "cloud", "both"))
    evaluation.add_argument("--no-rerank", action="store_true")
    evaluation.add_argument("--no-graph", action="store_true")
    commands.add_parser("check")
    return parser


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    pipeline: HybridPipeline | None = None
    try:
        pipeline = HybridPipeline(args.config)
        if args.command == "doctor":
            result = pipeline.doctor()
        elif args.command == "index":
            result = pipeline.index(providers=args.providers)
        elif args.command == "status":
            result = pipeline.status()
        elif args.command == "search":
            result = pipeline.search(args.query, mode=args.mode, rerank=not args.no_rerank, graph=not args.no_graph)
        elif args.command == "ask":
            result = pipeline.ask(args.question, mode=args.mode)
        elif args.command == "evaluate":
            result = evaluate(pipeline, args.queries, modes=args.modes, rerank=not args.no_rerank, graph=not args.no_graph)
        else:
            result = pipeline.check()
        _emit(result)
        if args.command == "index" and any(item["status"] != "complete" for item in result["providers"]):
            return 1
        if args.command == "doctor" and not result["healthy"]:
            return 1
        if args.command == "check" and any(item["status"] == "fail" for item in result["checks"]):
            return 1
        return 0
    except NLKEError as exc:
        _emit({"error": type(exc).__name__, "message": str(exc)})
        return 2
    except Exception as exc:
        _emit({"error": type(exc).__name__, "message": str(exc)})
        return 1
    finally:
        if pipeline is not None:
            pipeline.close()


if __name__ == "__main__":
    raise SystemExit(main())
