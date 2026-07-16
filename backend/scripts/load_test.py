"""Dependency-free HTTP smoke/load gate for a deployed API."""
import argparse
import concurrent.futures
import statistics
import time
import urllib.request


def request(url: str, timeout: float) -> tuple[float, int]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return time.perf_counter() - started, response.status
    except Exception:
        return time.perf_counter() - started, 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()
    with concurrent.futures.ThreadPoolExecutor(args.concurrency) as pool:
        results = list(pool.map(lambda _: request(args.url, args.timeout), range(args.requests)))
    latencies = sorted(item[0] * 1000 for item in results)
    p95 = latencies[max(0, round(len(latencies) * 0.95) - 1)]
    errors = sum(status < 200 or status >= 400 for _, status in results) / len(results)
    print({"requests": len(results), "p95_ms": round(p95, 2),
           "mean_ms": round(statistics.mean(latencies), 2), "error_rate": errors})
    return 0 if p95 <= args.max_p95_ms and errors <= args.max_error_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
