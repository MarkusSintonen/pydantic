import json
import time
from collections import defaultdict

from pydantic._internal._generate_schema import GenerateSchema


def perf():
    counts: dict[str, int] = defaultdict(int)
    timings: dict[str, float] = defaultdict(float)
    orig = GenerateSchema._generate_schema_inner

    def patch(self, obj):
        key = str(obj)
        counts[key] += 1
        s = time.monotonic()
        res = orig(self, obj)
        timings[key] += time.monotonic() - s
        return res

    # GenerateSchema._generate_schema_inner = patch

    start = time.monotonic()
    import k8s_v2

    count = {k: v for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=False) if v > 1}
    timings = {k: v for k, v in sorted(timings.items(), key=lambda x: x[1], reverse=False)}
    print("timings", json.dumps(timings, indent=2))
    print("counts", json.dumps(count, indent=2))
    print("took", time.monotonic() - start)


if __name__ == '__main__':
    perf()
