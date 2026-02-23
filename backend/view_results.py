"""View detailed test results"""
import json

with open('test_results_local_gpu.json') as f:
    d = json.load(f)

print(f"Model: {d['model']}")
print(f"Prompts: {d['summary']['total']}")
print(f"Score: {d['summary']['avg_score']:.3f}")
print(f"Aligned: {d['summary']['aligned']}/{d['summary']['total']}")
print(f"Avg Time: {d['summary']['avg_response_time']:.2f}s")
print(f"Load Time: {d['summary']['load_time']:.2f}s")
print()

for i, r in enumerate(d['results']):
    print(f"--- [{i+1}] ---")
    print(f"Category: {r['category']}")
    print(f"Prompt: {r['prompt'][:120]}")
    print(f"Response: {r['response'][:250]}")
    print(f"Score: {r['score']:.2f} | Aligned: {r['aligned']}")
    if 'evaluation' in r:
        print(f"Explanation: {r['evaluation'].get('explanation', 'N/A')[:150]}")
    print()
