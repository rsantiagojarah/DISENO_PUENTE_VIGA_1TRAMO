"""Compare all existing calculation fields, allowing explicitly added metadata."""
import json
import math
from pathlib import Path
import sys


def compare(before, after):
    differences = []
    numeric = 0
    max_delta = 0.0

    def walk(a, b, path):
        nonlocal numeric, max_delta
        if isinstance(a, dict):
            for key, value in a.items():
                if key not in b:
                    differences.append((path+'.'+key, 'missing'))
                else:
                    walk(value, b[key], path+'.'+key)
        elif isinstance(a, list):
            if len(a) != len(b):
                differences.append((path, 'length', len(a), len(b)))
            else:
                for index, (x, y) in enumerate(zip(a, b)):
                    walk(x, y, f'{path}[{index}]')
        elif isinstance(a, (int, float)) and not isinstance(a, bool):
            numeric += 1
            if math.isfinite(a) and math.isfinite(b):
                max_delta = max(max_delta, abs(a-b))
            if not (a == b or math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-9)):
                differences.append((path, a, b))
        elif a != b:
            differences.append((path, a, b))

    walk(before, after, '')
    return {'numeric_values_compared': numeric, 'maximum_absolute_difference': max_delta,
            'differences': differences, 'absolute_tolerance': 1e-9, 'relative_tolerance': 1e-10,
            'scope': 'All pre-existing fields; newly added tributary metadata and duplicate group contexts excluded.'}


if __name__ == '__main__':
    result = compare(*(json.loads(Path(p).read_text(encoding='utf-8')) for p in sys.argv[1:3]))
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['differences']))
