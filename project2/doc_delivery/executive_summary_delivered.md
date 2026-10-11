# Executive Risk Summary

## Overview

In October 2026 the AI Security Engineering Team tested three FinanceGuard AI systems in a non-production environment: the receipt classifier that screens expense claims, the expense policy chatbot, and the infrastructure the chatbot runs on. Five types of attacks were tested and every one succeeded at least partly. 

The most urgent problems
- Any employee using the expense chatbot can get it to reveal confidential executive salary and bonus details by asking ordinary questions. 
- The receipt classifier can be tricked into accepting fraudulent or non-receipt images, and that weaknesses in how the chatbot is deployed would make a breach worse. 

Most of the fixes are inexpensive, and the most serious one can be made within a day.

## Risk Dashboard

| System | Risk Level | Key Finding |
|--------|-----------|-------------|
| RAG Chatbot | CRITICAL | Reveals confidential executive compensation to any user; can be manipulated into ignoring its instructions |
| Receipt Classifier | HIGH | Can be fooled into accepting non-receipt images, opening a path to expense fraud |
| Deployment Infrastructure | HIGH | Runs with full administrative privileges, so any compromise of the chatbot becomes a much larger breach |

## Findings Summary

### 1. Confidential Executive Compensation Exposed Through the Chatbot — CRITICAL

**Business Impact:** A restricted document intended only for the Compensation Committee and CHRO is available to anyone who can use the chatbot. All six of our test questions reached it. Using everyday wording, such as asking for help with a "benchmarking report," we obtained the salary ranges for every executive level up to the CEO, plus bonus formulas, stock option terms and the clawback policy. If this leaked, FinanceGuard would face employee relations damage, retention risk, a possible privacy or regulatory issue, and harm to its reputation. No technical skill is needed to exploit it.

### 2. Receipt Classifier Can Be Tricked Into Approving Fake Receipts — HIGH

**Business Impact:** By making changes to an image that are barely visible, we caused the classifier to make the wrong decision most of the time. Its accuracy fell from 94% to 30%. In one test it accepted a photo of a car as a valid receipt. Someone submitting expenses could use this to get unsupported claims past automated screening, which leads directly to financial loss and audit exposure.

### 3. Deployment Infrastructure Grants Excessive Privileges — HIGH

**Business Impact:** The chatbot runs with full administrative rights, and its server includes tools an attacker could use to download malicious software or move data out. On their own, these settings do not cause a breach. If the chatbot is compromised, however, they turn a contained incident into a much more serious one.

### 4. Training Data Can Be Corrupted to Weaken Fraud Detection — MEDIUM

**Business Impact:** Someone who can change the training data can quietly weaken the classifier. Mislabeling fewer than 5% of the training images made the classifier accept about 1 in 5 non-receipts, compared with almost none before. Overall accuracy changed only modestly, so this kind of tampering could go unnoticed. The risk is rated MEDIUM because the attacker would need inside access to the training process.

### 5. Chatbot Can Be Manipulated Into Ignoring Its Rules — MEDIUM

**Business Impact:** Carefully worded requests got the chatbot to follow instructions slipped in by an attacker instead of its own. In one case it told an employee they could expense a $2,000 personal watch as a "client gift." Employees acting on wrong policy advice could submit claims the policy prohibits, and there is reputational risk if manipulated answers are shared. The effect is limited to the user's own conversation and no data was exposed, so the risk is MEDIUM.

## Prioritized Remediation

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 1 | Remove the confidential compensation document from the chatbot's knowledge base immediately, and review the knowledge base for any other restricted content | Low (hours) | Eliminates the CRITICAL exposure right away |
| 2 | Lock down the chatbot's deployment: run it with minimal privileges and remove unneeded tools | Low (1–2 days) | Limits the damage from any future breach of the chatbot |
| 3 | Require human review for low-confidence receipt decisions and high-value claims while the classifier is being hardened | Low–Medium (1–2 weeks) | Stops fraudulent receipts from being approved automatically |
| 4 | Add access controls so the chatbot shows each user only the documents they are allowed to see, and separate user input from the chatbot's instructions | Medium (4–6 weeks) | Prevents this whole class of data leaks and makes the chatbot harder to manipulate |
| 5 | Harden the classifier against manipulated images, and restrict and audit who can change training data | Medium–High (1–2 months) | Lasting protection against expense fraud and quiet tampering with the model |

## Conclusion

FinanceGuard's AI systems are useful, but they were deployed without the access controls and safeguards we expect for systems that handle sensitive financial and personnel data. 

Our top recommendation is to remove the confidential compensation document from the chatbot today. The fix takes hours, and until it is done any employee can see executive pay details. 

Within the next two weeks, the chatbot's deployment should be locked down and human review added for questionable receipts. 

Over the following quarter, leadership should fund document-level access controls for the chatbot and hardening of the classifier, so that AI systems are held to the same data-protection standards as the rest of the business.
