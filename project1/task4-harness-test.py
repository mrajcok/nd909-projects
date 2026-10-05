"""Task 4 test 2: per-request model override to a model not on the harness role's allow-list.

Run with the Streamlit app's .env loaded (AGENTCORE_HARNESS_ARN, AWS credentials):

    set -a; . ../cd15147-Foundations-Operational-AI-Security/project/streamlit_app/.env; set +a
    uv run --no-project --with 'boto3>=1.43.52' python task4-harness-test.py

Expected: AccessDeniedException on ConverseStream for the Nova inference profile.
"""
import os
import uuid

import boto3

HARNESS_ARN = os.environ["AGENTCORE_HARNESS_ARN"]
client = boto3.client("bedrock-agentcore", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def run(label, **override):
    print(f"\n=== {label}")
    try:
        response = client.invoke_harness(
            harnessArn=HARNESS_ARN,
            runtimeSessionId=str(uuid.uuid4()),
            messages=[{"role": "user", "content": [{"text": "What is Northstar's hybrid work policy? Name the source document."}]}],
            **override,
        )
        answer = ""
        for event in response["stream"]:
            if "contentBlockDelta" in event:
                answer += event["contentBlockDelta"]["delta"].get("text", "")
            elif "messageStop" in event:
                print("stopReason:", event["messageStop"]["stopReason"])
            elif "runtimeClientError" in event:
                print("runtimeClientError:", event["runtimeClientError"])
        print("answer:", answer[:300] or "(none)")
    except Exception as e:
        print(f"{type(e).__name__}: {e}")


run("Override to Nova 2 Lite (expect AccessDenied)",
    model={"bedrockModelConfig": {"modelId": "us.amazon.nova-2-lite-v1:0", "apiFormat": "converse_stream"}})
