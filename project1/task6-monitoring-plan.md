# Task 6: Monitoring Plan — Northstar Assist

What to log and watch to monitor how Northstar Assist behaves. Log group names, field names, and baselines below come from the live account (891975886417, us-east-1) as of 2026-10-04.

## 1. Logs and metrics

| Source | Where | What it gives us | Notes |
|---|---|---|---|
| Bedrock model invocation log | Log group /aws/bedrock/vantage-aria/invocations | One `ConverseStream` record per model call: system prompt, user prompt, `toolUse` the model asked for, `toolResult` with retrieved chunks and S3 URIs, answer, `stopReason`, token counts, guardrail trace. | This is the main source for every AI-specific signal. |
| Guardrail metrics | CloudWatch namespace AWS/Bedrock/Guardrails | `Invocations`, `InvocationsIntervened`, etc. | It  doesn't separate PROMPT_ATTACK from other content filters. The invocation log has that detail. |
| Model metrics | CloudWatch namespace AWS/Bedrock, dimension `ModelId` | `Invocations`, `InputTokenCount`, etc. | Cost and volume. |
| Harness runtime log | Log group /aws/bedrock-agentcore/runtimes/harness_NorthstarAssist-Wx7fEx65rH-DEFAULT | OpenTelemetry logs and other metrics from the harness container. | Useful for runtime errors and throttling. |
| Knowledge base application log | Log group /aws/vendedlogs/bedrock/knowledge-base/APPLICATION_LOGS/W44L9RLXWO | One event per document per ingestion job. | Shows when a document entered or changed in the KB, which matters for indirect injection. Doesn't record who uploaded it. |

**Gaps:**
- No user identity. `identity.arn` is the harness role plus a harness-generated session ID (`BedrockAgentCore-<uuid>`). But that's expected from the course setup.
- No uploader identity for S3. Server access logging is off on `northstar-assist-kb-mr774`, and CloudTrail isn't accessible in the course environment.
- No traces. CloudWatch GenAI Observability needs Transaction Search, which isn't available in the course environment either.

Baseline (from Northstar records so far): a knowledge base question produces two model turns. The `tool_use` turn has ~1,177 input / ~84 output tokens. The `end_turn` turn has ~3,870–3,890 input / ~200–280 output tokens. A blocked input produces one turn with 0 tokens.

**Configuration finding:**
I had AI (Opus 5.5) review the tools being offered to the model. It found that tools `shell` and `file_operations` are available in addition to the KB Retrieve tool. So, a prompt injection that gets the model to call `shell` runs commands in the harness container under the harness execution role. Signal 2 (below) watches for this, but the harness's `allowedTools` should probably be restricted to just the knowledge base tool. (I'd be curious to know what Udacity staff thinks of this finding.)

## 2. AI-specific signals

### Signal 1: Guardrail blocks a prompt attack (alerted)

What: invocation records when the Northstar guardrail blocked a user's input with the PROMPT_ATTACK filter. The record has `stopReason = guardrail_intervened` and `trace.guardrail.inputAssessment.mxjmq78m0lzs.contentPolicy.filters[].type = PROMPT_ATTACK` with `action = BLOCKED`.

Why it matters: employees asking about policies shouldn't trigger it. One block is probably someone curious. Several in a short window means someone is trying variations to find a phrasing that gets through.

Alert condition: alert when 3 or more PROMPT_ATTACK blocks occur within 15 minutes.
- Baseline is zero. In normal use, nothing should trigger it.
- 3 in 15 minutes filters out a single curious attempt but catches iterative probing early.
- The alarm counts across all sessions, because CloudWatch alarms can't group by session.

Implementation:

1. A metric filter on the invocation log turns each blocked prompt attack into a data point. The pattern was checked with `aws logs test-metric-filter` against real records: it matched the blocked "Ignore all previous instructions…" record and not a normal guarded answer.

   ```bash
   aws logs put-metric-filter \
     --log-group-name /aws/bedrock/vantage-aria/invocations \
     --filter-name NorthstarPromptAttackBlocks \
     --filter-pattern '{ $.output.outputBodyJson.trace.guardrail.inputAssessment.mxjmq78m0lzs.contentPolicy.filters[0].type = "PROMPT_ATTACK" && $.output.outputBodyJson.trace.guardrail.inputAssessment.mxjmq78m0lzs.contentPolicy.filters[0].action = "BLOCKED" }' \
     --metric-transformations metricName=PromptAttackBlocks,metricNamespace=NorthstarAssist,metricValue=1,defaultValue=0
   ```

2. An SNS topic could be created for the on-call analyst, and the alarm sent to that topic.

Limits:
- The pattern checks the first content filter in the trace. If another content filter also fires and is listed first, that block isn't counted.
- It only sees what the guardrail catches. A rephrased attack that passes the guardrail isn't caught/counted; signal 2 looks for what happens next.
- Topic policy blocks (`topicPolicy.topics[].action = BLOCKED`) aren't counted here. They are more likely to be false positives, so they're reviewed with query A in the playbook.

### Signal 2: Tool-use and retrieval anomalies (must be reviewed, not alerted)

What: model calls where the model's tool use doesn't match how Northstar should work. Every answer should come from one or more `northstar-kb___Retrieve` calls, and no other tool should ever be called. Anomalies are:
- A `toolUse` named `shell` or `file_operations`. Northstar has no legitimate use for either (as discussed above), so any call is suspicious.
- An `end_turn` answer in a session with no `toolResult`: the model answered without searching the knowledge base, so the answer is ungrounded, despite the system prompt.
- An `end_turn` answer with output tokens well above the ~200–280 baseline (for example over 1,000), especially without a retrieval: possible system prompt dump, off-topic generation, or bulk data listing.

Why it matters: these show a prompt injection that worked. The guardrail didn't catch it, and the model did something it shouldn't.

How: the Logs Insights queries C and D in the IR playbook. They're run during any incident.
