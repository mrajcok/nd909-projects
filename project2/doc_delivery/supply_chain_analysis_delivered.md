# Supply Chain Vulnerability Analysis

## Vulnerability Summary

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 34 |
| MEDIUM | 160 |
| LOW | 601 |
| UNKNOWN | 9 |
| **Total** | **804** |

## High Severity Findings

No CRITICAL CVEs were reported, but 34 HIGH findings were. The large majority come from `linux-libc-dev` (kernel headers, 6.12.74-2) and currently have **no fixed version available** from the distro — they are in the base image. Two HIGH findings are in Python packages and *do* have fixes (see next section). Representative sample:

| CVE | Package | Fixed Version | Description |
|-----|---------|--------------|-------------|
| CVE-2026-25210 | libexpat1 2.7.1-2 | none | Information disclosure / data integrity issues in libexpat |
| CVE-2021-3847 | linux-libc-dev 6.12.74-2 | none | Low-privileged user privilege escalation |
| CVE-2021-3864 | linux-libc-dev 6.12.74-2 | none | Descendant's dumpable setting with certain SUID binaries |
| CVE-2024-21803 | linux-libc-dev 6.12.74-2 | none | Bluetooth use-after-free in af_bluetooth.c |
| CVE-2024-58093 | linux-libc-dev 6.12.74-2 | none | PCI/ASPM use-after-free during hot-unplug |
| CVE-2025-38187 | linux-libc-dev 6.12.74-2 | none | drm/nouveau use-after-free in r535_gsp_rpc_push() |
| CVE-2025-38206 | linux-libc-dev 6.12.74-2 | none | Double free in exFAT filesystem |
| CVE-2019-19814 | linux-libc-dev 6.12.74-2 | none | Out-of-bounds write in __remove_dirty_segment (f2fs) |

(Top 15 are captured in `attacks/results/05_supply_chain/supply_chain_report.json` under `high_severity_vulnerabilities`.)

## Python-Specific Vulnerabilities

All Python-package findings are HIGH and, unlike the kernel headers, have fixes available. So, these are the most actionable items in the scan:

| CVE | Package | Installed | Fixed Version | Risk |
|-----|---------|-----------|--------------|------|
| CVE-2026-23949 | jaraco.context | 5.3.0 | 6.1.0 | Path traversal via a malicious tar archive |
| CVE-2026-24049 | wheel | 0.45.1 | 0.46.2 | Privilege escalation / arbitrary code execution via a malicious wheel |

These are build/packaging-time dependencies pulled in with the Python toolchain. Both are fixed by a simple upgrade and should be pinned with the fixed versions.

## Dockerfile Issues

6 issues found (1 HIGH, 3 MEDIUM, 2 LOW).

### 1. Container runs as root — HIGH

**Risk:** No `USER` directive is present, so the app runs as root.

**Fix:** Create a non-root user and add `USER appuser` before the `CMD`.

### 2. Base image not pinned to a digest — MEDIUM

**Risk:** `FROM python:3.11-slim` does not have a `@sha256` digest. The tag can be repointed upstream, so builds are not reproducible and a poisoned image could be pulled silently.

**Fix:** Specify a digest, e.g. `FROM python:3.11-slim@sha256:<digest>`.

### 3. Entire build context copied into image — MEDIUM

**Risk:** `COPY . /app` pulls the entire build context into the image, which can bake in secrets (`.env`, keys, `.git` history) and unneeded files that enlarge the attack surface. In this repo that context includes the RAG policy data, including the confidential compensation document.

**Fix:** Copy only what is needed and add a `.dockerignore` excluding `.git`, `.env`, credentials, and local artifacts.

### 4. No HEALTHCHECK defined — LOW

**Risk:** Without a `HEALTHCHECK` the orchestrator cannot tell a hung or crashed process from a healthy one, delaying detection of a compromised or failed container.

**Fix:** Add a `HEALTHCHECK` that probes the Flask health endpoint on port 5001.

### 5. Build tools present in production image — MEDIUM

**Risk:** Compilers/build tools (`build-essential`, `gcc`) remain in the image. They are not needed at runtime and give an attacker tooling to compile exploits in place.

**Fix:** Use a multi-stage build: compile in a builder stage and copy only runtime artifacts into the final image.

### 6. Unnecessary network/utility tools installed — LOW

**Risk:** `curl` and `git` are installed but not needed at runtime. They are useful to an attacker for downloading payloads or exfiltrating data from a shell.

**Fix:** Remove these packages from the runtime image, or install them only in a build stage.

## AI Pipeline Risk Assessment

These supply-chain issues map directly onto the RAG chatbot's security posture:

- **Model/data integrity.** `COPY . /app` with no `.dockerignore` ships the entire repo — including `rag_chatbot/data/policies/executive_bonus_structure_CONFIDENTIAL.md` — into the image. Anyone who can pull the image gets the confidential data. An unpinned base image means the foundation the whole pipeline runs on can change out from under it without notice.
- **Dependency security.** The two fixable Python HIGH CVEs (`wheel`, `jaraco.context`) are packaging-stage code-execution / path-traversal flaws. This is the stage where a malicious package could compromise the build and, by extension, the model-serving artifact. The bulk of the OS CVEs are unfixable kernel-header issues inherited from the base image, which is why pinning and slimming the base matters.
- **Runtime privileges.** The container runs as **root** with build tools and network utilities (`gcc`, `curl`, `git`) present. If the app is compromised the attacker can become root with a compiler and a downloader already in place. An app-level issue escalates into a full container-level backdoor.

## Remediation Priority

| Priority | Action |
|----------|--------|
| 1 | Drop root: add a non-root `USER`. Add a `.dockerignore` so secrets and the confidential policy data stop being copied into the image. |
| 2 | Upgrade the fixable Python HIGH CVEs and pin the package versions.
| 3 | Pin the base image to a digest, use a multi-stage build to strip out build tools from the final image, and rebuild on a patched base to remove inherited OS CVEs. Add a `HEALTHCHECK`. |
