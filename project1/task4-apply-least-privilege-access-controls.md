# Task 4: Apply Least-Privilege Access Controls — Northstar Assist

## 1. Request path
```
Employee → Streamlit app → InvokeHarness → harness [harness execution role] 
→ Bedrock ConverseStream (Haiku) harness [harness execution role]
→ InvokeGateway → gateway [gateway service role] 
→ bedrock:Retrieve → KB
```

| Gateway service role |  |

## 2. Harness execution role
`arn:aws:iam::891975886417:role/service-role/AmazonBedrockAgentCoreHarnessDefaultServiceRole-zijuj`

**Trust policy:** `bedrock-agentcore.amazonaws.com` only, conditioned on `aws:SourceAccount` = 891975886417 and `aws:SourceArn` like `arn:aws:bedrock-agentcore:us-east-1:891975886417:*`. Acceptable; no change.

**Permission policies:** two customer managed policies, each attached only to this role.

### 2.1 Original permissions

#### 2.1.1. AmazonBedrockAgentCoreHarnessGatewayPolicy_pg4rz (v1)

| Sid | Actions | Resource | Assessment |
|---|---|---|---|
| AgentCoreGatewayAccess | `bedrock-agentcore:InvokeGateway` | `gateway/northstar-assist-gateway-jsp1gqv8r0` | keep |

#### 2.1.2. AmazonBedrockAgentCoreHarnessExecutionPolicy_ujplo (v1)

Wow, there are a lot of actions associated with this role!

| Sid | Actions | Resource | Assessment |
|---|---|---|---|
| BedrockModelInvocation | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` | `arn:aws:bedrock:*::foundation-model/*`, `arn:aws:bedrock:us-east-1:891975886417:*` | Too broad. Allow every foundation model in every Region, plus every Bedrock resource in the account. |
| BedrockMantleInference | `bedrock-mantle:CreateInference` | `arn:aws:bedrock-mantle:us-east-1:891975886417:*` | Not used |
| BedrockMantleCallWithBearerToken | `bedrock-mantle:CallWithBearerToken` | `*` | Not used |
| EcrPublicTokenAccess | `ecr-public:GetAuthorizationToken` | `*` | Runtime. Keep. |
| StsForEcrPublicPull | `sts:GetServiceBearerToken` | `*` | Runtime. Keep. |
| EcrManagedImagePull | `ecr:BatchGetImage`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchCheckLayerAvailability` | `arn:aws:ecr:us-east-1:*:repository/harness-*` | Runtime. Keep. |
| EcrManagedImageToken | `ecr:GetAuthorizationToken` | `*` | Runtime. Keep. |
| XRayTracingAccess | `xray:PutTraceSegments`, `PutTelemetryRecords`, `GetSamplingRules`, `GetSamplingTargets` | `*` | Runtime. Keep the Put actions. |
| CloudWatchLogsGroup | `logs:CreateLogGroup`, `logs:DescribeLogStreams` | `log-group:/aws/bedrock-agentcore/runtimes/*` | Too broad. Allows every runtime's log group, not just Northstar's. |
| CloudWatchLogsDescribeGroups | `logs:DescribeLogGroups` | `log-group:*` | Too broad. Lists every log group in the account. |
| CloudWatchLogsStream | `logs:CreateLogStream`, `logs:PutLogEvents` | `log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*` | Too broad. Lets harness write into other runtimes' logs (for example `harness_VantageAria-*`). |
| CloudWatchLogsPutResourcePolicy | `logs:PutResourcePolicy` | `log-group:/aws/bedrock-agentcore/runtimes/harness_NorthstarAssist-*` | Not needed. |
| CloudWatchMetricsPublish | `cloudwatch:PutMetricData` | `*` (namespace `bedrock-agentcore`) | Not used. |
| AgentCoreWorkloadIdentity | `bedrock-agentcore:GetWorkloadAccessToken`, `GetWorkloadAccessTokenForJWT` | workload identity directory and `harness_NorthstarAssist-*` | Runtime. Keep. |
| AgentCoreBrowserDefault | 7 Browser session actions | `arn:aws:bedrock-agentcore:us-east-1:aws:browser/*` | Not configured. Gives the agent a web browser, a data-exfiltration path for prompt injection. |
| AgentCoreCodeInterpreterDefault | 5 Code Interpreter actions | `arn:aws:bedrock-agentcore:us-east-1:aws:code-interpreter/*` | Not configured. Arbitrary code execution. |
| EFSClientAccess / EFSDescribe | `elasticfilesystem:ClientMount`, `ClientWrite`, `DescribeAccessPoints`, `DescribeMountTargets` | every file system and access point in the account | Not configured. Mount and write any EFS file system in the account. |
| S3FilesClientAccess / S3FilesDescribe | `s3files:ClientMount`, `ClientWrite`, `ClientRootAccess`, `GetAccessPoint`, `ListMountTargets` | every S3 Files file system in the account | Not configured. Includes root access. |
| AgentCoreMemory | `CreateEvent`, `DeleteEvent`, `GetEvent`, `ListEvents`, `RetrieveMemoryRecords` | `memory/NorthstarAssist-*` | Not configured. The harness has memory disabled. |
| *(missing)* | `bedrock:ApplyGuardrail` | — | Needed once a guardrail is attached in Task 5 |

### 2.2 Last Accessed

11 services granted, 5 used:

| Service | Last used | Keep or Remove |
|---|---|---|
| `bedrock` | 2026-10-01 23:28 UTC | Keep |
| `bedrock-agentcore` | 2026-10-01 23:28 UTC | Keep |
| `ecr-public` | 2026-10-02 03:07 UTC (`GetAuthorizationToken`) | Keep |
| `logs` | 2026-10-02 03:08 UTC (`CreateLogGroup`, `CreateLogStream`) | Keep |
| `xray` | 2026-10-01 23:28 UTC | Keep |
| `bedrock-mantle` | never | Remove |
| `cloudwatch` | never | Remove |
| `elasticfilesystem` | never | Remove |
| `s3files` | never | Remove |
| `ecr` | never | but keep, since DEMO.md keeps it |
| `sts` | never | but keep, since DEMO.md keeps it |

Browser, Code Interpreter, and Memory are under `bedrock-agentcore`, so Last Accessed can't separate them from `InvokeGateway`. The harness config (`tools`: one gateway, `memory: disabled`, `skills: []`) shows they aren't used.

### 2.3 Policy Issues

Any principal that can call `InvokeHarness` can pass a per-request `model`, system prompt, and tools. `InvokeHarness` has no condition keys, so the caller's policy can't block an override. The harness execution role makes the model call, so its model allow-list is the only control over which model an override runs. With the original settings, any model can be used.

Guardrails are out of scope for this task and will be added in task 5.

### 2.4 Policy Changes

Replaced both managed policies with what is below.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeHaiku45Only",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:us-east-1:891975886417:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0"
      ]
    },
    {
      "Sid": "InvokeNorthstarGateway",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:InvokeGateway",
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:891975886417:gateway/northstar-assist-gateway-jsp1gqv8r0"
    },
    {
      "Sid": "RuntimeLogs",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:DescribeLogStreams", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": [
        "arn:aws:logs:us-east-1:891975886417:log-group:/aws/bedrock-agentcore/runtimes/harness_NorthstarAssist-*",
        "arn:aws:logs:us-east-1:891975886417:log-group:/aws/bedrock-agentcore/runtimes/harness_NorthstarAssist-*:log-stream:*"
      ]
    },
    {
      "Sid": "RuntimeImageAndTelemetry",
      "Effect": "Allow",
      "Action": ["ecr-public:GetAuthorizationToken", "sts:GetServiceBearerToken", "xray:PutTraceSegments", "xray:PutTelemetryRecords", "ecr:GetAuthorizationToken"],
      "Resource": "*"
    },
    {
      "Sid": "RuntimeManagedImagePull",
      "Effect": "Allow",
      "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
      "Resource": "arn:aws:ecr:us-east-1:*:repository/harness-*"
    },
    {
      "Sid": "WorkloadIdentity",
      "Effect": "Allow",
      "Action": ["bedrock-agentcore:GetWorkloadAccessToken", "bedrock-agentcore:GetWorkloadAccessTokenForJWT"],
      "Resource": [
        "arn:aws:bedrock-agentcore:us-east-1:891975886417:workload-identity-directory/default",
        "arn:aws:bedrock-agentcore:us-east-1:891975886417:workload-identity-directory/default/workload-identity/harness_NorthstarAssist-*"
      ]
    }
  ]
}
```

What changed, and what didn't:
- Models: one model/inference profile for Haiku 4.5, plus the two ARNs that `get-inference-profile` lists for it.
- Gateway: unchanged, one ARN.
- Logs: narrowed from every runtime to `harness_NorthstarAssist-*`. `DescribeLogGroups` on `*` and `PutResourcePolicy` dropped.
- Removed: `bedrock-mantle`, `cloudwatch:PutMetricData`, `xray:GetSampling*`, Browser, Code Interpreter, EFS, S3 Files, Memory, and model invocation on every other model and account resource.
- No S3 and no Retrieve: the harness only reaches the knowledge base through the gateway.

## 3. Gateway service role
`arn:aws:iam::891975886417:role/service-role/AmazonBedrockAgentCoreGatewayDefaultServiceRole1790822056513`

**Trust policy:** `bedrock-agentcore.amazonaws.com` only, conditioned on `aws:SourceAccount` = 891975886417 and `aws:SourceArn` like `gateway/northstar-assist-gateway-*`. Acceptable; no change.

**Permission policies:** two customer managed policies, each attached only to this role.

### 3.1 Original permissions

#### 3.1.1 AmazonBedrockAgentCoreGatewayKBAccessProd_79B9C3

| Sid | Actions | Resource | Condition | Assessment |
|---|---|---|---|---|
| AllowBedrockGetKnowledgeBaseFromKnowledgeBase | `bedrock:GetKnowledgeBase` | `knowledge-base/W44L9RLXWO` | — | Keep |
| AllowBedrockRetrieveFromKnowledgeBase | `bedrock:Retrieve` | `knowledge-base/W44L9RLXWO` | — | Keep |
| AllowBedrockAgenticRetrieveStream | `bedrock:AgenticRetrieveStream` | `*` | none | Too broad. Allows agentic retrieval from any knowledge base in the account (for example Aria's). |
| AllowBedrockInvokeModelForKnowledgeBase | `bedrock:InvokeModel`, `InvokeModelWithResponseStream` | `foundation-model/*` (all Regions), and all account inference profiles, provisioned and custom models | `aws:CalledVia` = `bedrock.amazonaws.com` | Too broad. Allows every model. The condition limits it to calls Bedrock makes on the role's behalf, but plain Retrieve doesn't need it. |
| AllowBedrockRerankForKnowledgeBase | `bedrock:Rerank` | `*` | `aws:CalledVia` | Not needed for Retrieve |
| AllowBedrockGetInferenceProfileForKnowledgeBase | `bedrock:GetInferenceProfile` | `inference-profile/*` | `aws:CalledVia` | Not needed |
| AllowBedrockApplyGuardrailForKnowledgeBase | `bedrock:ApplyGuardrail` | `guardrail/*` | `aws:CalledVia` | Too broad. Allows every guardrail in the account; the gateway applies none. |

#### 3.1.2 AmazonBedrockAgentCoreGatewayBasePolicyProd_DEF4C8

| Sid | Actions | Resource | Assessment |
|---|---|---|---|
| GetGateway | `bedrock-agentcore:GetGateway` | `gateway/northstar-assist-gateway-*` | Although scoped by prefix, narrow to the one gateway ARN. |
| GetConfigurationBundleVersion | `bedrock-agentcore:GetConfigurationBundleVersion` | `configuration-bundle/*` (same account, us-east-1) | Keep |

### 3.2 IAM Last Accessed

| Service | Last used |
|---|---|
| `bedrock` | 2026-10-01 23:28 UTC |
| `bedrock-agentcore` | never |

`bedrock-agentcore` has never been used in my project yet, but the demo kept the two base actions and the gateway was verified working with them. Keep them. Removing them is a candidate for a later, re-tested change.

### 3.3 Policy Issues

The gateway only needs to read and retrieve from one knowledge base. `bedrock:AgenticRetrieveStream` on `*` has no condition, so the role's credentials can run agentic retrieval against any knowledge base in the account, including Aria's (which I still have running). The knowledge base scoping on `Retrieve` doesn't help when a second retrieval action is open to every knowledge base.

The `InvokeModel*`, `Rerank`, `GetInferenceProfile`, and `ApplyGuardrail` statements carry `aws:CalledVia` = `bedrock.amazonaws.com`, so they work only when Bedrock makes the call on the role's behalf, not with stolen credentials directly. They still cover every model, every inference profile, and every guardrail in the account, and plain `Retrieve` doesn't need any of them, so they are removed.

`GetGateway` is scoped by the `northstar-assist-gateway-*` prefix rather than the one gateway ARN, so it would also cover any future gateway created with that prefix.

### 3.4 Policy Changes

Replaced both managed policies with the following:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadOwnGateway",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:GetGateway",
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:891975886417:gateway/northstar-assist-gateway-jsp1gqv8r0"
    },
    {
      "Sid": "ReadConfigBundle",
      "Effect": "Allow",
      "Action": "bedrock-agentcore:GetConfigurationBundleVersion",
      "Resource": "arn:aws:bedrock-agentcore:us-east-1:891975886417:configuration-bundle/*",
      "Condition": {
        "StringEquals": {
          "aws:ResourceAccount": "${aws:PrincipalAccount}",
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "RetrieveFromNorthstarKbOnly",
      "Effect": "Allow",
      "Action": ["bedrock:GetKnowledgeBase", "bedrock:Retrieve"],
      "Resource": "arn:aws:bedrock:us-east-1:891975886417:knowledge-base/W44L9RLXWO"
    }
  ]
}
```

What changed and what didn't:
- Knowledge base: `GetKnowledgeBase` and `Retrieve` unchanged, on the one Northstar knowledge base.
- Gateway: `GetGateway` narrowed from the `northstar-assist-gateway-*` prefix to the one gateway ARN.
- Configuration bundle: `GetConfigurationBundleVersion` unchanged, with its account and Region conditions.
- Removed: `AgenticRetrieveStream` on `*`, `Rerank` on `*`, all `InvokeModel*`, `GetInferenceProfile`, and `ApplyGuardrail` on `guardrail/*`.
- No S3 and no model access: the knowledge base reads documents and creates embeddings under its own service role.

## 4. How changes were applied

(My notes, in case I need to do this again. E.g., if my Project 1 submission requires any rework.)

1. Harness role: on the role's Permissions tab, Add permissions → Create inline policy → JSON, paste section 2.4's JSON, check Access Analyzer validation (Security / Errors / Warnings / Suggestions all 0), save as `northstar-harness-execution-scoped`. Then detach (don't delete) `AmazonBedrockAgentCoreHarnessExecutionPolicy_ujplo` and `AmazonBedrockAgentCoreHarnessGatewayPolicy_pg4rz`, so they can be reattached to roll back.
2. Gateway role: add section 3.4's JSON inline as `northstar-gateway-kb-scoped`, validate, then detach `AmazonBedrockAgentCoreGatewayKBAccessProd_79B9C3` and `AmazonBedrockAgentCoreGatewayBasePolicyProd_DEF4C8`.

How to test/verify changes:

| Request | Expected after scoping |
|---|---|
| "What is Northstar's hybrid work policy? Name the source document." | Retrieve tool call succeeds, answer cites the Company Policies Handbook |
| `invoke_harness(..., model={"bedrockModelConfig": {"modelId": "us.amazon.nova-2-lite-v1:0", "apiFormat": "converse_stream"}})` | Denied: `runtimeClientError` wrapping `AccessDeniedException` on `ConverseStream` (model not on the allow-list) |

If the first request fails, a request-path permission is missing. If the second succeeds, the model allow-list isn't in effect.

## 5. Blast radius: before and after

| Role | Problems with original permissions | With fixed/scoped permissions |
|---|---|---|
| Harness execution role | Attacker can invoke any foundation model in any Region and any Bedrock model resource in the account; run inference through `bedrock-mantle`; start Browser sessions (web access, exfiltration) and Code Interpreter sessions (code execution); mount and write any EFS or S3 Files file system with root access; read and delete Memory events; write into other runtimes' log groups; enumerate all log groups. | Invoke Claude Haiku 4.5 only; call the one Northstar gateway; write its own runtime logs. |
| Gateway service role | Run agentic retrieval against any knowledge base in the account, including Aria's; through Bedrock, invoke any model, rerank, and apply any guardrail. | Read and retrieve from the Northstar knowledge base only. |

**Summary:** the harness role goes from every model and six unused capabilities to one model and one gateway; the gateway role goes from any knowledge base and any model to one knowledge base.

## 6. AI findings

I asked AI (Opus 5.5) to review Northstar's policies. Here are the findings:

- **`allowedTools: ["*"]` on the harness:** any tool later added to the gateway is exposed to the model automatically. Replace with an explicit list.
- **Caller credentials:** the Streamlit app uses the lab's `voclabs` session credentials, not a dedicated role. A production caller role should allow only `bedrock-agentcore:InvokeHarness` and `bedrock-agentcore:InvokeAgentRuntime` on the harness ARN. The harness role's model allow-list is what limits a caller's per-request model override.
- **Guardrail (next task):** the harness has no guardrail, and the role has no `bedrock:ApplyGuardrail`. A caller's per-request override can still run without one until the next task adds the guardrail, `ApplyGuardrail` on it, and a Deny on model calls that don't carry it. [We knew it would find this.]
- **KB service role** (`AmazonBedrockExecutionRoleForKnowledgeBase_c8x2h`): out of scope here. Its default `cloudwatch:PutMetricData` and `aws-marketplace` statements on `*` are not needed for sync.
- **Access Analyzer validation alone isn't enough:** it reports 0 findings for over-broad policies. Add custom policy checks (`check-access-not-granted` for actions such as `bedrock-agentcore:StartBrowserSession` and `bedrock:DeleteGuardrail`) in CI for future policy changes.
