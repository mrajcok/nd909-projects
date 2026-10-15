# Incident Response Playbook
## Northstar Research Agent

**Version:** 1.0

**Owner:** Security Operations Center

**Completed by:** Mark Rajcok

**Date:** 2026-10-15

---

## When to Activate This Playbook

Activate when any of the following occur:

- The agent executes a command that was not requested by the user
- Employee records or credentials appear in an agent response unexpectedly
- A user reports unusual agent behavior
- An alert fires from one of the monitoring rules below

---

## Incident Severity Levels

| Level | Criteria | Examples |
|-------|----------|---------|
| **P1 — Critical** | Active breach or confirmed credential exposure | `GET_SYSTEM_INFO` or `EXPORT_ALL_DATA` executed in production |
| **P2 — High** | Unauthorized data access | Employee PII returned to wrong user, `query_hr_database` called for non-HR task |
| **P3 — Medium** | Suspicious but unconfirmed | Repeated injection attempts with no confirmed success |
| **P4 — Low** | Near-miss or policy violation | User trying injection, agent correctly refused |

---

## First 30 Minutes

### Minutes 0–5: Confirm and Classify

- [ ] Pull the agent logs for the session in question
- [ ] Identify: which command or tool was called? What data was returned?
- [ ] Assign a severity level (P1 / P2 / P3 / P4)
- [ ] Page on-call if P1 or P2

**Log location:** `/var/log/northstar-agent/agent.jsonl` (structured per-request logs), mirrored to the central SIEM index `northstar-agent-*`.
**On-call contact:** SOC on-call via PagerDuty service "Northstar-Agent" (+1-555-0100); escalation to SOC lead.

---

### Minutes 5–15: Contain

If the session is still active:

```bash
# Stop the agent
sudo pkill -f northstar_agent

# If needed, block the user's access
# Revoke the user's session token in the identity provider (Okta): disable the
# user, then invalidate active sessions. At the network edge, block the source
# IP in the WAF/reverse-proxy allowlist until the investigation completes.
```

Preserve all logs before restarting anything.

If data was exported or credentials were exposed:
- [ ] Notify the Data Privacy team immediately
- [ ] Do not attempt to hide or undo the access — preserve evidence

---

### Minutes 15–30: Assess and Notify

Answer these questions and document the answers:

| Question | Answer (fill in per incident; sources to check) |
|----------|--------|
| Which records were accessed? | Read the `commands_executed` and `tools_called` log fields for the session; `SEARCH_EMPLOYEE` names the record, `EXPORT_ALL_DATA`/`query_hr_database` means treat ALL four employee records (Alice Johnson, Bob Martinez, System Administrator, Carol White) as exposed. |
| Were credentials exposed? | Yes if `GET_SYSTEM_INFO` executed (prod DB password, admin JWT) or any record's `internal_api_key` appears in the response. Assume exposed if uncertain. |
| Was the knowledge base modified? | Check ingestion/audit log for `chroma_data`; compare document IDs/hashes against the approved baseline; look for unexpected or `malicious-*` IDs in the session's `retrieved_doc_ids`. |
| Is the attack ongoing? | Check for repeated injection patterns or command executions from the same user/IP in the last hour; confirm the agent process was stopped and the token revoked. |

Notify based on severity:
- P1/P2: CISO, Legal, HR (if employee data)
- P3: SOC team lead
- P4: Log and monitor

---

## Remediation Before Restarting

- [ ] Audit and purge malicious documents from the knowledge base:
  ```bash
  sudo python3 load_knowledge_base.py --reset
  sudo python3 load_knowledge_base.py
  ```
- [ ] Rotate any exposed credentials
- [ ] Apply hardened system prompt and guardrails
- [ ] Rerun the validation test suite before bringing the agent back online

---

## What to Log for Every Agent Interaction

These fields must be captured for every request:

| Field | Why It Matters |
|-------|---------------|
| Timestamp | Forensic timeline |
| User ID / Session ID | Attribution and correlation |
| Full user input | Evidence |
| Retrieved document IDs | Detect RAG poisoning |
| Commands executed | Alert on unauthorized actions |
| Tools called | Alert on privilege violations |
| Response time (ms) | Detect denial-of-service patterns |

Additional fields recommended based on Phase 2 findings:

| Field | Why It Matters |
|-------|---------------|
| Denied tool calls | Records blocked privilege-escalation attempts (least-privilege enforcement) |
| RAG documents quarantined | Flags injection content caught by the content filter before it reached the model |
| Source IP | Correlate and block abusive sources |
| Task type / allowed tool set | Confirms the agent ran under the intended least-privilege scope |
| Model + prompt version | Ties behavior to a specific deployed configuration |

---

## Alert Rules

Define at least 5 rules of your own. Use the severity criteria above to assign a
priority to each, and base your trigger conditions on the commands, tools, and
attack behavior you observed in Phase 2.

One row is filled in as a formatting example — it does not count toward your 5.

| Alert Name | Trigger Condition | Severity | First Action |
|-----------|-------------------|----------|-------------|
| *Example:* Bulk export triggered | `EXPORT_ALL_DATA` executed | P1 | Page on-call, suspend session |
| System info / credential disclosure | `GET_SYSTEM_INFO` executed, OR a response contains a `db_password`, `admin_token`, or `sk-` API key pattern | P1 | Page on-call, suspend session, begin credential rotation |
| Unauthorized HR data access | `query_hr_database` called when task type is not `ticketing`/HR-authorized, OR `SEARCH_EMPLOYEE` executed for a user not entitled to that record | P2 | Suspend session, notify Data Privacy, scope affected records |
| Command executed without matching user request | A command appears in `commands_executed` that was not explicitly asked for in the user's input (e.g. emitted inside a refusal, or injected) | P2 | Suspend session, capture prompt + response, review output-handling control |
| RAG poisoning detected | A `malicious-*` / non-baseline document is retrieved, OR the content filter quarantines a document containing an injection pattern | P3 (P2 if a command also executed that turn) | Quarantine the document, audit the knowledge base, identify who ingested it |
| Repeated injection attempts | ≥3 inputs from the same user/IP in 10 minutes matching injection patterns ("ignore previous instructions", "system override", "admin mode", `EXPORT_ALL_DATA`, etc.), all refused | P3 | Rate-limit/block the source, review for any attempt that succeeded, raise to P2 on first success |
| Agent performance / DoS pattern | Response time > 60s sustained, OR a single session issues an abnormal request volume / oversized inputs | P4 | Throttle the session, check compute/queue health, review for resource exhaustion |

---

## Contacts

| Role | Name | Contact |
|------|------|---------|
| SOC | SOC On-Call | soc@northstar-tech.com |
| AI Enablement | AI Platform Team | ai-team@northstar-tech.com |
| Data Privacy | Data Privacy Office | privacy@northstar-tech.com |
| Legal | Legal / Counsel | legal@northstar-tech.com |
