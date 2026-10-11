"""
FGSM (Fast Gradient Sign Method) Evasion Attack

Performs a white-box adversarial attack on the ReceiptCNN by computing
gradient-based perturbations that fool the classifier.

The FGSM formula is: x_adv = x + epsilon * sign(grad_x(loss))

Usage:
    python 01_fgsm_evasion.py
    python 01_fgsm_evasion.py --model-path ../classifier/checkpoints/receipt_cnn_clean.pt
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "classifier"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from model import ReceiptCNN

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results", "01_fgsm")


def fgsm_attack(image, epsilon, data_grad):
    """
    Apply FGSM perturbation to an image.

    Args:
        image: Original input image tensor
        epsilon: Perturbation magnitude
        data_grad: Gradient of the loss w.r.t. the input image

    Returns:
        Perturbed image tensor, clamped to valid pixel range [0, 1]
    """
    sign_data_grad = data_grad.sign()
    perturbed_image = image + epsilon * sign_data_grad
    perturbed_image = torch.clamp(perturbed_image, 0.0, 1.0)
    return perturbed_image.detach()


def evaluate_fgsm(model_path, test_dir, epsilon):
    """
    Run FGSM attack across the entire test set and return metrics.

    Args:
        model_path: Path to model checkpoint
        test_dir: Path to test dataset directory
        epsilon: FGSM perturbation magnitude

    Returns:
        Dictionary with clean_accuracy, adversarial_accuracy, attack_success_rate
    """
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])

    dataset = datasets.ImageFolder(test_dir, transform=transform)
    loader = DataLoader(dataset, batch_size=1, shuffle=False)

    model = ReceiptCNN().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    clean_correct = 0
    adv_correct = 0
    flipped = 0
    total = 0

    for image, label in loader:
        image = image.to(DEVICE)
        label_t = label.float().unsqueeze(1).to(DEVICE)

        image.requires_grad = True

        output = model(image)
        clean_is_correct = ((output > 0.5).float() == label_t).item()

        loss = torch.nn.BCELoss()(output, label_t)
        model.zero_grad()
        loss.backward()

        perturbed_image = fgsm_attack(image, epsilon, image.grad.data)

        with torch.no_grad():
            adv_output = model(perturbed_image)
        adv_is_correct = ((adv_output > 0.5).float() == label_t).item()

        total += 1
        if clean_is_correct:
            clean_correct += 1
            if not adv_is_correct:
                flipped += 1
        if adv_is_correct:
            adv_correct += 1

    return {
        "epsilon": epsilon,
        "clean_accuracy": clean_correct / total if total > 0 else 0,
        "adversarial_accuracy": adv_correct / total if total > 0 else 0,
        "attack_success_rate": flipped / clean_correct if clean_correct > 0 else 0,
        "total_samples": total,
    }


def visualize_fgsm(model_path, test_dir, epsilon, sample_index=0, output_dir="."):
    """Save a clean/adversarial FGSM comparison for a single test image."""
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])

    dataset = datasets.ImageFolder(test_dir, transform=transform)
    if len(dataset) == 0:
        raise ValueError(f"No images found in test directory: {test_dir}")
    if sample_index >= len(dataset):
        raise IndexError(
            f"sample_index {sample_index} is outside dataset with {len(dataset)} images"
        )

    image, label = dataset[sample_index]
    image_path, _ = dataset.samples[sample_index]
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    safe_image_name = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in image_name
    )
    class_name = dataset.classes[label]

    model = ReceiptCNN().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    image = image.unsqueeze(0).to(DEVICE)
    label_t = torch.tensor([[float(label)]], device=DEVICE)
    image.requires_grad = True

    output = model(image)
    clean_pred = (output > 0.5).float()
    loss = torch.nn.BCELoss()(output, label_t)
    model.zero_grad()
    loss.backward()

    perturbed_image = fgsm_attack(image, epsilon, image.grad.data)

    with torch.no_grad():
        adv_output = model(perturbed_image)
    adv_pred = (adv_output > 0.5).float()

    clean_label = dataset.classes[int(clean_pred.item())]
    adv_label = dataset.classes[int(adv_pred.item())]
    clean_conf = output.item()
    adv_conf = adv_output.item()

    clean_np = image.detach().cpu().squeeze(0).permute(1, 2, 0).numpy()
    adv_np = perturbed_image.detach().cpu().squeeze(0).permute(1, 2, 0).numpy()

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].imshow(clean_np)
    axes[0].set_title(f"Clean\nPred: {clean_label} ({clean_conf:.3f})")
    axes[0].axis("off")

    axes[1].imshow(adv_np)
    axes[1].set_title(f"FGSM epsilon={epsilon:g}\nPred: {adv_label} ({adv_conf:.3f})")
    axes[1].axis("off")

    fig.suptitle(
        f"{image_name} | True: {class_name} | epsilon={epsilon:g}",
        fontsize=12,
    )
    fig.tight_layout()

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(
        output_dir,
        f"fgsm_results_{safe_image_name}_{epsilon:g}.png",
    )
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="FGSM Evasion Attack")
    parser.add_argument(
        "--model-path",
        default=os.path.join(os.path.dirname(__file__),
                             "..", "classifier", "checkpoints", "receipt_cnn_clean.pt"),
    )
    parser.add_argument(
        "--test-dir",
        default=os.path.join(os.path.dirname(__file__),
                             "..", "classifier", "balanced_data", "test"),
    )
    parser.add_argument("--output", default=os.path.join(RESULTS_DIR, "fgsm_results.json"))
    args = parser.parse_args()
    if not os.path.dirname(args.output):
        args.output = os.path.join(RESULTS_DIR, args.output)
    results_dir = os.path.dirname(args.output)
    os.makedirs(results_dir, exist_ok=True)

    epsilons = [0.0, 0.01, 0.03, 0.05, 0.1, 0.15]
    results = []

    print(f"Model: {args.model_path}")
    print(f"Test dir: {args.test_dir}")
    print(f"\n{'Epsilon':>10} {'Clean Acc':>12} {'Adv Acc':>12} {'Attack Rate':>12}")
    print("-" * 50)

    for eps in epsilons:
        r = evaluate_fgsm(args.model_path, args.test_dir, eps)
        results.append(r)
        visualize_fgsm(args.model_path, args.test_dir, eps, output_dir=results_dir)
        print(f"{eps:>10.3f} {r['clean_accuracy']:>12.4f} {r['adversarial_accuracy']:>12.4f} {r['attack_success_rate']:>12.4f}")

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
