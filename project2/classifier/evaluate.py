"""
Evaluate a trained ReceiptCNN checkpoint.

Prints accuracy, precision, recall, F1, and confusion matrix.

Usage:
    python evaluate.py                                              # Evaluate clean model
    python evaluate.py --model-path checkpoints/receipt_cnn_poisoned.pt  # Evaluate poisoned model
    python evaluate.py --results-dir results/evaluation             # Save JSON and confusion matrix
"""
import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from model import ReceiptCNN
from data import get_transform

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")


def evaluate_model(model_path, test_dir):
    transform = get_transform()
    dataset = datasets.ImageFolder(test_dir, transform=transform)
    loader = DataLoader(dataset, batch_size=32, shuffle=False)

    model = ReceiptCNN().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    y_true = []
    y_pred = []

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(DEVICE)
            outputs = model(images)
            preds = (outputs > 0.5).int().squeeze(1).cpu().numpy()
            y_pred.extend(preds.tolist())
            y_true.extend(labels.numpy().tolist())

    metrics = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
        "classes": dataset.classes,
    }
    return metrics


def print_metrics(metrics, label="Model"):
    print(f"\n{'=' * 40}")
    print(f"  {label}")
    print(f"{'=' * 40}")
    print(f"  Accuracy:  {metrics['accuracy']:.4f}")
    print(f"  Precision: {metrics['precision']:.4f}")
    print(f"  Recall:    {metrics['recall']:.4f}")
    print(f"  F1 Score:  {metrics['f1']:.4f}")
    print(f"  Confusion Matrix:")
    cm = metrics["confusion_matrix"]
    print(f"    [[{cm[0][0]:4d}, {cm[0][1]:4d}]")
    print(f"     [{cm[1][0]:4d}, {cm[1][1]:4d}]]")
    print(f"{'=' * 40}")


def save_metrics(metrics, output_dir, label="Model"):
    """Save evaluation metrics as JSON and a confusion matrix PNG."""
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "metrics.json")
    with open(json_path, "w") as f:
        json.dump({"label": label, **metrics}, f, indent=2)

    cm = metrics["confusion_matrix"]
    classes = metrics.get("classes", ["class_0", "class_1"])

    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax.set_xticks(range(len(classes)))
    ax.set_yticks(range(len(classes)))
    ax.set_xticklabels(classes)
    ax.set_yticklabels(classes)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(
        "Confusion Matrix\n"
        f"Acc: {metrics['accuracy']:.4f} | Prec: {metrics['precision']:.4f} | "
        f"Recall: {metrics['recall']:.4f} | F1: {metrics['f1']:.4f}"
    )

    max_value = max(max(row) for row in cm) if cm else 0
    threshold = max_value / 2
    for row_idx, row in enumerate(cm):
        for col_idx, value in enumerate(row):
            color = "white" if value > threshold else "black"
            ax.text(col_idx, row_idx, value, ha="center", va="center", color=color)

    fig.tight_layout()
    png_path = os.path.join(output_dir, "confusion_matrix.png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    print(f"Metrics saved to: {json_path}")
    print(f"Confusion matrix saved to: {png_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate ReceiptCNN")
    parser.add_argument(
        "--model-path", default="checkpoints/receipt_cnn_clean.pt",
        help="Path to model checkpoint"
    )
    parser.add_argument(
        "--test-dir", default="balanced_data/test",
        help="Path to test dataset directory"
    )
    parser.add_argument(
        "--results-dir", default="",
        help="Optional folder for metrics.json and confusion_matrix.png. "
             "If omitted, results are only printed."
    )
    args = parser.parse_args()

    metrics = evaluate_model(args.model_path, args.test_dir)
    print_metrics(metrics, label=args.model_path)
    if args.results_dir:
        save_metrics(metrics, args.results_dir, label=args.model_path)
