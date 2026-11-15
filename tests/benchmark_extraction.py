"""Opt-in live-provider benchmark over ten labeled synthetic multilingual posts."""
import argparse
import json
import time
from pathlib import Path

from opportunityos.extraction import extract
from opportunityos.extraction_provider import generate


def normalize(value):
    return sorted(v.casefold() for v in value) if isinstance(value, list) else value.casefold().strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("ollama", "local_chat", "regex"), default="ollama")
    parser.add_argument("--model", default="qwen3:4b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, default=Path("outputs/extraction-benchmark.json"))
    args = parser.parse_args()
    cases = json.loads((Path(__file__).parent / "fixtures/multilingual_posts.json").read_text())
    results = []
    for case in cases:
        response = {}
        def audited_provider(messages, schema, settings):
            document = generate(messages, schema, settings)
            response.update(document)
            return document
        started = time.monotonic()
        item = extract({"raw_text": case["text"], "source_link": "https://example.invalid/benchmark/" + case["id"]},
                       {"extraction_provider": args.provider, "extraction_model": args.model,
                        "extraction_endpoint": args.endpoint, "extraction_threshold": .8}, audited_provider)
        values = {key: field["value"] for key, field in item["field_evidence"].items()}
        correct = {key: normalize(values[key]) == normalize(value) for key, value in case["expected"].items()}
        row = {"id": case["id"], "engine": item["extraction_engine"], "model": args.model,
               "seconds": round(time.monotonic() - started, 2), "correct": sum(correct.values()), "total": len(correct),
               "fields": item["field_evidence"], "raw_response": response,
               "errors": {key: {"expected": case["expected"][key], "actual": values[key]} for key in correct if not correct[key]}}
        results.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
        print(case["id"], str(row["correct"]) + "/" + str(row["total"]), row["engine"], flush=True)
    print("Exact fields",sum(r["correct"] for r in results),"/",sum(r["total"] for r in results),flush=True)


if __name__ == "__main__":
    main()
