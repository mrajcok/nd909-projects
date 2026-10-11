"""
Dataset preparation utilities for the Receipt Classifier.

Handles dataset balancing (downsampling majority class) and
provides DataLoader creation functions.

Usage:
    python data.py --source /path/to/raw/data --target balanced_data
"""
import os
import shutil
import random
import argparse
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def prepare_balanced_dataset(source_root, target_root, seed=42):
    """
    Creates a balanced dataset by downsampling non_receipt class
    to match receipt count. Preserves train/test split.
    """
    random.seed(seed)

    for split in ["train", "test"]:
        receipt_dir = os.path.join(source_root, split, "receipt")
        non_receipt_dir = os.path.join(source_root, split, "non_receipt")

        receipt_files = [
            f for f in os.listdir(receipt_dir)
            if os.path.isfile(os.path.join(receipt_dir, f))
            and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ]
        non_receipt_files = [
            f for f in os.listdir(non_receipt_dir)
            if os.path.isfile(os.path.join(non_receipt_dir, f))
            and os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ]

        target_count = len(receipt_files)
        sampled_non_receipts = random.sample(non_receipt_files, target_count)

        for cls, files, src_dir in [
            ("receipt", receipt_files, receipt_dir),
            ("non_receipt", sampled_non_receipts, non_receipt_dir),
        ]:
            out_dir = os.path.join(target_root, split, cls)
            os.makedirs(out_dir, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(src_dir, f), os.path.join(out_dir, f))
            print(f"[{split}] {cls}: {len(files)} images")

    print(f"\nBalanced dataset created at {target_root}")


def get_transform(train=False):
    if train:
        return transforms.Compose([
            transforms.RandomCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(10),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
        ])
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
    ])


def get_data_loaders(data_root, batch_size=32):
    train_transform = get_transform(train=True)
    test_transform = get_transform(train=False)
    train_dataset = datasets.ImageFolder(
        os.path.join(data_root, "train"), transform=train_transform
    )
    test_dataset = datasets.ImageFolder(
        os.path.join(data_root, "test"), transform=test_transform
    )
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=2)
    return train_loader, test_loader


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare balanced dataset")
    parser.add_argument(
        "--source", required=True,
        help="Path to raw unbalanced dataset (with train/ and test/ subdirs)"
    )
    parser.add_argument(
        "--target", default="balanced_data",
        help="Output directory for balanced dataset (default: balanced_data)"
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    prepare_balanced_dataset(args.source, args.target, args.seed)
