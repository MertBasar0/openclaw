import json
import argparse
import sys

def evaluate_checklist(takeoff_path):
    with open(takeoff_path, 'r') as f:
        data = json.load(f)
    summary = data.get("summary", data)
    totals = summary.get("totals", summary)
    
    results = {
        "passedChecks": [],
        "failedChecks": [],
        "warnings": [],
        "evidence": {},
        "severity": "low"
    }

    # Check 1: Has elements
    element_count = summary.get("elementCount", data.get("elementCount", 0))
    if element_count > 0:
        results["passedChecks"].append("Model has elements")
    else:
        results["failedChecks"].append("Model is empty")
        results["severity"] = "high"

    # Check 2: Slab presence
    if totals.get("slabAreaM2", data.get("slabAreaM2", 0)) > 0:
        results["passedChecks"].append("Slab detected")
    else:
        results["warnings"].append("No slab area found")

    # Check 3: Diagnostics
    diagnostics = data.get("diagnostics", []) or summary.get("diagnostics", [])
    if not diagnostics:
        results["passedChecks"].append("No diagnostic warnings")
    else:
        results["failedChecks"].append("Diagnostics reported issues")
        results["severity"] = "high"
        results["evidence"]["diagnostics"] = diagnostics

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--takeoff", required=True, help="Path to takeoff JSON")
    parser.add_argument("--output", required=True, help="Path to output checklist JSON")
    args = parser.parse_args()

    try:
        results = evaluate_checklist(args.takeoff)
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Checklist evaluation complete. Output saved to {args.output}")
    except Exception as e:
        print(f"Error evaluating checklist: {e}", file=sys.stderr)
        sys.exit(1)
