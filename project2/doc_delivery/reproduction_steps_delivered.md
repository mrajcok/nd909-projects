# Reproduction Steps

## Prerequisites

- **Python:** 3.12.13
- **Python packages:** the set in `requirements.txt` (torch, torchvision, scikit-learn, numpy, Pillow, matplotlib, flask, faiss-cpu, openai, python-dotenv, requests)
- **OpenAI API key:** used by the RAG chatbot (any OpenAI-compatible endpoint)
- **curl:** for the chatbot smoke test
- **Hardware:** CPU only; no GPU required, but GPU acceleration is recommended. `train.py` uses CUDA or Apple MPS if available, otherwise it falls back to CPU.

All commands below start from the repository root (the directory containing `requirements.txt`) unless a step says otherwise.

## Environment Setup

```bash
# Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# Install pinned dependencies
pip install -r requirements.txt

# Configure API credentials for the RAG chatbot
cp .env.example rag_chatbot/.env
# Edit rag_chatbot/.env:
#   OPENAI_API_KEY=your-openai-api-key
#   OPENAI_BASE_URL=https://api.openai.com/v1
```

## Step 1: Prepare Dataset

No preparation is needed. The balanced dataset provisioned for this engagement is at `classifier/balanced_data/` (with `train/` and `test/` subdirectories) and is used as is.

```bash
# Confirm the balanced dataset is present
ls classifier/balanced_data/train classifier/balanced_data/test
```

## Step 2: Train and Evaluate Clean Model

The current release checkpoint, `classifier/checkpoints/receipt_cnn_clean.pt`, is used as the clean baseline. It is not retrained, and per the Rules of Engagement it is never overwritten. Evaluating it also records the clean baseline metrics that the poisoning comparison in Step 4 needs.

```bash
cd classifier
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt --test-dir balanced_data/test
cd ..
```

Expected: more than 94% accuracy on the balanced test set. The observed result was accuracy 0.9436, precision 0.9943, recall 0.8923 and F1 0.9405.

## Step 3: FGSM Attack

```bash
cd attacks
python 01_fgsm_evasion.py
cd ..
```

The script evaluates the clean checkpoint against `classifier/balanced_data/test` at epsilon values 0.0, 0.01, 0.03, 0.05, 0.10 and 0.15.

Expected output:
- A table of clean accuracy, adversarial accuracy and attack success rate for each epsilon, also saved to `attacks/results/01_fgsm/fgsm_results.json`
- One side-by-side clean vs. adversarial image per epsilon, saved as `attacks/results/01_fgsm/fgsm_results_<image_name>_<epsilon>.png`
- Adversarial accuracy falls below 50% at epsilon 0.05 (observed: 0.3000)

## Step 4: Data Poisoning

```bash
# 1. Create the poisoned dataset (defaults: --flip-rate 0.05 --seed 42)
cd attacks
python 02_label_flip_poisoning.py

# 2. Retrain on the poisoned data into a separate checkpoint
cd ../classifier
python train.py --data-dir poisoned_data --checkpoint-name receipt_cnn_poisoned.pt

# 3. Evaluate the poisoned model on the clean test set
python evaluate.py --model-path checkpoints/receipt_cnn_poisoned.pt --test-dir balanced_data/test --results-dir ../attacks/results/02_label_flip/poisoned

# 4. Evaluate the clean model for comparison
python evaluate.py --model-path checkpoints/receipt_cnn_clean.pt --test-dir balanced_data/test --results-dir ../attacks/results/02_label_flip/clean
cd ..
```

Expected output:
- 56 of 1,154 training labels flipped (28 in each direction); a label-flip visualization saved to `attacks/results/02_label_flip/label_flip_results_5.png`
- `metrics.json` and `confusion_matrix.png` in both `attacks/results/02_label_flip/poisoned/` and `attacks/results/02_label_flip/clean/`
- Poisoned model: accuracy 0.8949, precision 0.8348, recall 0.9846, F1 0.9035. Non-receipts accepted as receipts (false positives) rise from 1 to 38.

## Step 5: RAG Chatbot Setup

```bash
cd rag_chatbot
python build_index.py    # Build the FAISS index (if not already built)
python app.py            # Start the Flask server on port 5001 (leave it running)
```

In a second terminal, test with a legitimate query:

```bash
curl -X POST http://localhost:5001/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the meal expense limit?"}'
```

Expected output:
- `build_index.py`: `Total chunks: ~23`, `FAISS index built: 23 vectors, dim=1536`, `Index saved to faiss_index/`
- The curl response says the limit is "$75 per person per meal", based on the expense policy

## Step 6: Prompt Injection

Requires the chatbot from Step 5 to be running.

```bash
cd attacks
python 03_prompt_injection.py
cd ..
```

Results are saved under `attacks/results/03_prompt_injection/`. LLM output is non-deterministic, so individual responses may vary between runs.

## Step 7: Data Exfiltration

Requires the chatbot from Step 5 to be running.

```bash
cd attacks
python 04_data_exfiltration.py
cd ..
```

Results are saved to `attacks/results/04_exfiltration/data_exfiltration_results.json`.

## Step 8: Supply Chain Analysis

This step is static analysis only. It reads the Trivy report (`06_trivy_report.json`) and `Dockerfile` supplied by the system owner; no scan or image build is needed.

```bash
cd attacks
python 05_supply_chain_analysis.py
cd ..
```

Results are saved to `attacks/results/05_supply_chain/supply_chain_report.json`.

## Expected Results Summary

| Attack | Metric | Expected Result |
|--------|--------|----------------|
| Clean baseline | Test accuracy | 0.9436 (precision 0.9943, recall 0.8923, F1 0.9405) |
| FGSM Evasion | Adversarial accuracy at ε=0.05 | 0.3000; below 50% at ε ≤ 0.10, as the charter requires |
| Label-Flip Poisoning (5%) | Accuracy / precision / false positives | Accuracy 0.9436 → 0.8949; precision 0.9943 → 0.8348; false positives 1 → 38 |
| Prompt Injection | Successful injections | 1 / 9 by automated scoring (Attempt 9, delimiter injection); 2 / 9 including the under-scored Role Hijacking variant (Attempt 7). Confidential source retrieved in 1 / 9 (Attempt 5) |
| Data Exfiltration | Queries exfiltrating confidential data | 6 / 6 retrieved `executive_bonus_structure_CONFIDENTIAL.md`; 5 / 6 leaked its contents in the answer |
| Supply Chain Analysis | Vulnerabilities / Dockerfile issues | 804 vulnerabilities (0 CRITICAL, 34 HIGH, 160 MEDIUM, 601 LOW, 9 UNKNOWN); 6 Dockerfile issues (1 HIGH, 3 MEDIUM, 2 LOW) |
