import json
import argparse
import sys

def run_review(takeoff_path, checklist_path, output_path):
    with open(takeoff_path, 'r') as f:
        takeoff = json.load(f)
    with open(checklist_path, 'r') as f:
        checklist = json.load(f)
    
    takeoff_summary = takeoff.get("summary", takeoff)
    totals = takeoff_summary.get("totals", takeoff_summary)
    element_count = takeoff_summary.get("elementCount", takeoff.get("elementCount", 0))
    failed_checks = checklist.get("failedChecks", [])
    warnings = checklist.get("warnings", [])
    
    summary = f"The model contains {element_count} elements, including a bounding box volume of {totals.get('boundingBoxVolumeM3', takeoff.get('boundingBoxVolumeM3', 0))} m3."
    risk_points = []
    if failed_checks:
        risk_points.extend(failed_checks)
    if warnings:
        risk_points.extend(warnings)
    if not risk_points:
        risk_points.append("No critical risks identified.")
        
    missing_metadata = ["Project phase not defined", "Author information missing"]
    
    next_steps = [
        "Review the missing metadata fields.",
        "Proceed with detailed design geometry."
    ]

    result = {
        "summary": summary,
        "risk_points": risk_points,
        "missing_metadata": missing_metadata,
        "next_steps": next_steps
    }

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print("--- DESIGN REVIEW COPILOT REPORT ---")
    print(f"Summary: {result['summary']}")
    print(f"Risk Points: {', '.join(result['risk_points'])}")
    print(f"Missing Metadata: {', '.join(result['missing_metadata'])}")
    print(f"Next Steps: {', '.join(result['next_steps'])}")
    print("------------------------------------")
    print(f"Report saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--takeoff", required=True, help="Path to takeoff JSON")
    parser.add_argument("--checklist", required=True, help="Path to checklist JSON")
    parser.add_argument("--output", required=True, help="Path to output review JSON")
    args = parser.parse_args()

    run_review(args.takeoff, args.checklist, args.output)
