"""Offline, deterministic SQL-validity and referenced-table evaluation gate."""
import argparse
import json
from pathlib import Path

from sqlglot import exp, parse_one


def tables(sql: str) -> set[str]:
    return {node.name.lower() for node in parse_one(sql, dialect="postgres").find_all(exp.Table)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path, help="JSON object mapping case id to SQL")
    parser.add_argument("--baseline", type=Path, default=Path("evaluation/baseline.json"))
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    valid = true_positive = predicted_count = expected_count = 0
    for case in baseline["cases"]:
        expected = set(case["expected_tables"])
        expected_count += len(expected)
        try:
            predicted = tables(predictions[case["id"]])
            valid += 1
        except Exception:
            predicted = set()
        true_positive += len(predicted & expected)
        predicted_count += len(predicted)
    count = len(baseline["cases"])
    valid_rate = valid / count
    precision = true_positive / predicted_count if predicted_count else 0
    recall = true_positive / expected_count if expected_count else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    print(json.dumps({"cases": count, "valid_sql_rate": valid_rate, "table_f1": f1}, indent=2))
    acceptance = baseline["acceptance"]
    return 0 if valid_rate >= acceptance["minimum_valid_sql_rate"] and f1 >= acceptance["minimum_table_f1"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
