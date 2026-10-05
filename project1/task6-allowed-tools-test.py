"""Check that Northstar still answers a normal question when the model is offered only the
knowledge base Retrieve tool (no shell or file_operations).

Uses the per-request `allowedTools` override on InvokeHarness, so the harness itself isn't changed.
Per the API docs, `allowedTools` entries are `*`, `@builtin`, `@serverName` (all tools from an MCP
server, here the AgentCore Gateway), or `@serverName/toolName`. Both gateway forms are tried. For each,
the script checks the streamed answer, then reads the Bedrock invocation log to see which tools the
model was actually offered (the `toolConfig` of the logged ConverseStream request).

Run with the Streamlit app's .env loaded (AGENTCORE_HARNESS_ARN, AWS credentials):

    set -a; . ../cd15147-Foundations-Operational-AI-Security/project/streamlit_app/.env; set +a
    uv run --no-project --with 'boto3>=1.43.52' python task6-allowed-tools-test.py
"""
import json
import os
import time
import uuid

import boto3
from botocore.config import Config

REGION = os.environ.get("AWS_REGION", "us-east-1")
HARNESS_ARN = os.environ["AGENTCORE_HARNESS_ARN"]
LOG_GROUP = "/aws/bedrock/vantage-aria/invocations"  # account-wide invocation log
QUESTION = "What is Northstar's hybrid work policy? Name the source document."
RETRIEVE = "northstar-kb___Retrieve"
GATEWAY = "northstar-assist-gateway-jsp1gqv8r0"  # harness tool name of the gateway (the MCP server)
CANDIDATES = [
    f"@{GATEWAY}",               # every tool the gateway exposes (today only Retrieve)
    f"@{GATEWAY}/{RETRIEVE}",    # just the Retrieve tool
]

# Limits so a bad candidate can't hang the run: the harness default allows 75 iterations and 3600 s.
HARNESS_TIMEOUT_S = 90
HARNESS_MAX_ITERATIONS = 6

agent = boto3.client(
    "bedrock-agentcore",
    region_name=REGION,
    config=Config(connect_timeout=10, read_timeout=HARNESS_TIMEOUT_S + 30, retries={"max_attempts": 1}),
)
logs = boto3.client("logs", region_name=REGION)


def ask(allowed):
    """Invoke the harness with allowedTools=[allowed]. Tag the question so its log records can be found."""
    tag = uuid.uuid4().hex[:8]
    text = f"{QUESTION} (ref {tag})"
    started = int(time.time() * 1000)
    result = {"allowed": allowed, "tag": tag, "started": started, "answer": "", "stops": [], "tools_called": [], "error": None}
    try:
        response = agent.invoke_harness(
            harnessArn=HARNESS_ARN,
            runtimeSessionId=str(uuid.uuid4()),
            messages=[{"role": "user", "content": [{"text": text}]}],
            allowedTools=[allowed],
            timeoutSeconds=HARNESS_TIMEOUT_S,
            maxIterations=HARNESS_MAX_ITERATIONS,
        )
        for event in response["stream"]:
            if "contentBlockStart" in event:
                tool = event["contentBlockStart"].get("start", {}).get("toolUse")
                if tool:
                    result["tools_called"].append(tool.get("name"))
            elif "contentBlockDelta" in event:
                result["answer"] += event["contentBlockDelta"]["delta"].get("text", "")
            elif "messageStop" in event:
                result["stops"].append(event["messageStop"]["stopReason"])
            elif "runtimeClientError" in event:
                result["error"] = event["runtimeClientError"].get("message")
    except Exception as e:  # noqa: BLE001 - report any failure as the result for this candidate
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def offered_tools(tag, started, wait_s=180):
    """Return the tool names offered to the model in the logged requests carrying this tag."""
    deadline = time.time() + wait_s
    while time.time() < deadline:
        offered, found = set(), False
        for page in logs.get_paginator("filter_log_events").paginate(
            logGroupName=LOG_GROUP, startTime=started - 60_000, filterPattern=f'"ref {tag}"'
        ):
            for event in page["events"]:
                try:
                    record = json.loads(event["message"])
                except json.JSONDecodeError:
                    continue
                found = True
                tools = record.get("input", {}).get("inputBodyJson", {}).get("toolConfig", {}).get("tools", [])
                offered.update(t["toolSpec"]["name"] for t in tools)
        if found:
            return sorted(offered)  # [] means the request was logged but offered no tools
        time.sleep(15)  # invocation logs can take a minute or two to arrive
    return None


def main():
    results = []
    for candidate in CANDIDATES:
        print(f"\nAsking with allowedTools=[{candidate!r}] ...", flush=True)
        r = ask(candidate)
        print(f"\n=== allowedTools=[{candidate!r}]")
        print("stop reasons:", r["stops"], "| tools called:", r["tools_called"])
        if r["error"]:
            print("error:", r["error"][:300])
        print("answer tail:", r["answer"][-200:].replace("\n", " ") or "(none)")
        results.append(r)

    print("\nWaiting for invocation logs ...")
    passed = []
    for r in results:
        r["offered"] = offered_tools(r["tag"], r["started"]) if not r["error"] else None
        answered = (
            "end_turn" in r["stops"]
            and RETRIEVE in r["tools_called"]
            and "Company Policies Handbook" in r["answer"]
        )
        retrieve_only = r["offered"] == [RETRIEVE]
        ok = answered and retrieve_only
        print(f"\n{r['allowed']!r}: offered={r['offered']} answered_from_kb={answered} retrieve_only={retrieve_only} -> {'PASS' if ok else 'FAIL'}")
        if ok:
            passed.append(r["allowed"])

    print("\nPASS:", passed or "none")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
