"""
Supply Chain Vulnerability Analysis.

Parses a Trivy JSON report and analyzes a Dockerfile for security issues.
Produces a structured risk assessment of the AI system's deployment pipeline.

Usage:
    python 05_supply_chain_analysis.py
    python 05_supply_chain_analysis.py --trivy-report ../06_trivy_report.json --dockerfile ../Dockerfile
"""
import json
import argparse
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "05_supply_chain")


def parse_trivy_report(path):
    """
    Parse a Trivy JSON report and extract vulnerability details.

    The Trivy JSON format has a "Results" array, where each result has:
    - "Target": what was scanned (e.g., "debian 13.4" or "Python")
    - "Type": scan type (e.g., "debian", "python-pkg")
    - "Vulnerabilities": array of vulnerability objects

    Each vulnerability has: VulnerabilityID, Severity, PkgName,
    InstalledVersion, FixedVersion, Title, Description

    Args:
        path: Path to Trivy JSON report

    Returns:
        List of vulnerability dictionaries
    """
    with open(path) as f:
        data = json.load(f)

    vulns = []

    for result in data.get("Results", []):
        target = result.get("Target", "")
        target_type = result.get("Type", "")
        for v in result.get("Vulnerabilities") or []:
            description = v.get("Description") or ""
            vulns.append({
                "id": v.get("VulnerabilityID", ""),
                "severity": v.get("Severity", "UNKNOWN"),
                "package": v.get("PkgName", ""),
                "installed_version": v.get("InstalledVersion", ""),
                "fixed_version": v.get("FixedVersion") or "",
                "title": v.get("Title", ""),
                "description": description[:200],
                "target": target,
                "target_type": target_type,
            })

    return vulns


def analyze_dockerfile(path):
    """
    Analyze a Dockerfile for common security issues.

    Check for:
    1. Running as root (no USER directive) — HIGH
    2. Unpinned base image (no SHA256 digest) — MEDIUM
    3. COPY . (copies entire context including secrets) — MEDIUM
    4. No HEALTHCHECK — LOW
    5. Build tools left in production image — MEDIUM
    6. Unnecessary tools (curl, git) in production — LOW

    Args:
        path: Path to Dockerfile

    Returns:
        List of issue dictionaries with: issue, severity, detail, recommendation
    """
    with open(path) as f:
        content = f.read()
    lines = content.strip().split("\n")

    issues = []

    # Ignore comments and blank lines for directive-based checks.
    directives = [
        ln.strip() for ln in lines
        if ln.strip() and not ln.strip().startswith("#")
    ]
    upper = content.upper()

    # 1. Running as root (no USER directive) — HIGH
    if not any(ln.upper().startswith("USER ") for ln in directives):
        issues.append({
            "issue": "Container runs as root",
            "severity": "HIGH",
            "detail": "No USER directive is present, so the process runs as root. "
                      "A compromise of the app then has root inside the container, "
                      "widening the blast radius of any container escape.",
            "recommendation": "Create a non-root user and add a 'USER appuser' "
                              "directive before the CMD.",
        })

    # 2. Unpinned base image (no SHA256 digest) — MEDIUM
    from_lines = [ln for ln in directives if ln.upper().startswith("FROM ")]
    if from_lines and not any("@sha256:" in ln.lower() for ln in from_lines):
        issues.append({
            "issue": "Base image not pinned to a digest",
            "severity": "MEDIUM",
            "detail": "The FROM image is referenced by tag (e.g. python:3.11-slim) "
                      "rather than an immutable @sha256 digest. The tag can be "
                      "repointed upstream, so builds are not reproducible and a "
                      "poisoned image could be pulled silently.",
            "recommendation": "Pin the base image to a specific digest, e.g. "
                              "FROM python:3.11-slim@sha256:<digest>.",
        })

    # 3. COPY . (copies entire build context, including secrets) — MEDIUM
    if any(ln.upper().startswith("COPY . ") or ln.upper().strip() == "COPY ."
           or ln.upper().startswith("ADD . ") for ln in directives):
        issues.append({
            "issue": "Entire build context copied into image",
            "severity": "MEDIUM",
            "detail": "'COPY . /app' pulls the whole build context into the image, "
                      "which can bake in secrets (.env, keys, .git history) and "
                      "unneeded files that enlarge the attack surface.",
            "recommendation": "Copy only what is needed, and add a .dockerignore "
                              "excluding .git, .env, credentials, and local artifacts.",
        })

    # 4. No HEALTHCHECK — LOW
    if "HEALTHCHECK" not in upper:
        issues.append({
            "issue": "No HEALTHCHECK defined",
            "severity": "LOW",
            "detail": "Without a HEALTHCHECK the orchestrator cannot tell a hung or "
                      "crashed process from a healthy one, delaying detection of a "
                      "compromised or failed container.",
            "recommendation": "Add a HEALTHCHECK that probes the app's health "
                              "endpoint (e.g. the Flask port 5001).",
        })

    # 5. Build tools left in the production image — MEDIUM
    build_tools = [t for t in ("build-essential", "gcc", "g++", "make")
                   if t in content]
    if build_tools:
        issues.append({
            "issue": "Build tools present in production image",
            "severity": "MEDIUM",
            "detail": "Compilers/build tools (" + ", ".join(build_tools) + ") remain "
                      "in the final image. They are not needed at runtime and give an "
                      "attacker tooling to compile exploits in place.",
            "recommendation": "Use a multi-stage build: compile in a builder stage "
                              "and copy only the runtime artifacts into a clean final "
                              "image.",
        })

    # 6. Unnecessary tools (curl, git) in production — LOW
    extra_tools = [t for t in ("curl", "git", "wget", "netcat", "nc")
                   if t in content]
    if extra_tools:
        issues.append({
            "issue": "Unnecessary network/utility tools installed",
            "severity": "LOW",
            "detail": "Tools (" + ", ".join(extra_tools) + ") are installed but not "
                      "needed at runtime. They are useful to an attacker for "
                      "downloading payloads or exfiltrating data from a shell.",
            "recommendation": "Remove these packages from the runtime image, or "
                              "install them only in a separate build stage.",
        })

    return issues


def generate_report(vulns, dockerfile_issues):
    """Generate a structured supply chain risk report."""
    # Generate a report dictionary with:
    # - "summary": total vulnerabilities, severity breakdown, dockerfile issue count
    # - "high_severity_vulnerabilities": list of HIGH severity CVEs (top 15)
    # - "python_specific": vulnerabilities in Python packages
    # - "dockerfile_issues": from analyze_dockerfile()
    # - "risk_assessment": overall risk level and key concerns

    severity_counts = {}
    for v in vulns:
        sev = v.get("severity", "UNKNOWN")
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    high_severity = [
        v for v in vulns if v.get("severity") in ("CRITICAL", "HIGH")
    ][:15]

    python_specific = [
        v for v in vulns if v.get("target_type") in ("python-pkg", "pip")
    ]

    critical = severity_counts.get("CRITICAL", 0)
    high = severity_counts.get("HIGH", 0)
    dockerfile_high = sum(1 for i in dockerfile_issues if i.get("severity") == "HIGH")

    if critical or dockerfile_high:
        risk_level = "CRITICAL"
    elif high:
        risk_level = "HIGH"
    elif severity_counts.get("MEDIUM", 0) or dockerfile_issues:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    key_concerns = []
    if critical:
        key_concerns.append(f"{critical} CRITICAL OS/package vulnerabilities")
    if high:
        key_concerns.append(f"{high} HIGH severity vulnerabilities")
    if python_specific:
        key_concerns.append(
            f"{len(python_specific)} vulnerabilities in Python dependencies"
        )
    for i in dockerfile_issues:
        if i.get("severity") == "HIGH":
            key_concerns.append(f"Dockerfile: {i['issue']}")

    report = {
        "summary": {
            "total_vulnerabilities": len(vulns),
            "severity_breakdown": severity_counts,
            "dockerfile_issues": len(dockerfile_issues),
        },
        "high_severity_vulnerabilities": high_severity,
        "python_specific": python_specific,
        "dockerfile_issues": dockerfile_issues,
        "risk_assessment": {
            "overall_risk": risk_level,
            "key_concerns": key_concerns,
        },
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Supply Chain Vulnerability Analysis")
    parser.add_argument(
        "--trivy-report",
        default=os.path.join(os.path.dirname(__file__), "..", "06_trivy_report.json"),
    )
    parser.add_argument(
        "--dockerfile",
        default=os.path.join(os.path.dirname(__file__), "..", "Dockerfile"),
    )
    parser.add_argument(
        "--output",
        default=os.path.join(RESULTS_DIR, "supply_chain_report.json"),
    )
    args = parser.parse_args()
    if not os.path.dirname(args.output):
        args.output = os.path.join(RESULTS_DIR, args.output)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)

    print("Parsing Trivy report...")
    vulns = parse_trivy_report(args.trivy_report)

    print("Analyzing Dockerfile...")
    dockerfile_issues = analyze_dockerfile(args.dockerfile)

    report = generate_report(vulns, dockerfile_issues)

    # Print summary
    print(f"\n{'=' * 50}")
    print("  SUPPLY CHAIN RISK ASSESSMENT")
    print(f"{'=' * 50}")
    s = report["summary"]
    print(f"\n  Total vulnerabilities: {s['total_vulnerabilities']}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        count = s["severity_breakdown"].get(sev, 0)
        if count:
            print(f"    {sev}: {count}")

    print(f"\n  Dockerfile issues: {s['dockerfile_issues']}")
    print(f"{'=' * 50}")

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report saved to {args.output}")


if __name__ == "__main__":
    main()
