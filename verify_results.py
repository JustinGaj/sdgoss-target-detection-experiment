"""Compare a real execution to the report archive, excluding variable timing."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verify(actual, expected):
    for key in ('seed', 'test_scope', 'thresholds', 'tests', 'warning'):
        if actual[key] != expected[key]:
            raise ValueError(f'Reproduction mismatch: {key}')
    for key, value in expected['geometry'].items():
        if not math.isclose(actual['geometry'][key], value, rel_tol=1e-12):
            raise ValueError(f'Reproduction mismatch: geometry.{key}')
    timing = actual['cpu_benchmark']
    if timing['samples'] != 30 or timing['warmup'] != 3:
        raise ValueError('Unexpected timing protocol')
    if not 0 < timing['p50_ms'] <= timing['p95_ms'] <= timing['max_ms']:
        raise ValueError('Invalid measured timing statistics')
    # Exclude the 9-pixel baseline from the four long-range conditions.
    rows = actual['tests']
    long_range = rows[1:5]
    negatives = rows[5:7]
    return {
        'status': 'PASS',
        'comparison': 'All seven detection counts and geometry match the report archive',
        'total_frames': sum(r['frames'] for r in rows),
        'long_range_recall_percent': 100 * sum(r['positive_frames'] for r in long_range)
                                     / sum(r['frames'] for r in long_range),
        'negative_frame_false_positive_percent': 100 * sum(r['positive_frames'] for r in negatives)
                                                / sum(r['frames'] for r in negatives),
        'timing_comparison': 'Excluded from equality check; independently measured each run',
        'measured_cpu_benchmark': timing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actual', type=Path, default=ROOT / 'results.json')
    parser.add_argument('--expected', type=Path, default=ROOT / 'results/report/results.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'verification.json')
    args = parser.parse_args()
    result = verify(json.loads(args.actual.read_text(encoding='utf-8')),
                    json.loads(args.expected.read_text(encoding='utf-8')))
    result['detector_script_sha256'] = hashlib.sha256((ROOT / 'detector_test.py').read_bytes()).hexdigest()
    result['actual_results_sha256'] = hashlib.sha256(args.actual.read_bytes()).hexdigest()
    result['verification_environment'] = {'platform': platform.platform(), 'python': platform.python_version()}
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
