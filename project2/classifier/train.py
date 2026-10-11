"""
Train the ReceiptCNN on a dataset.

Usage:
    python train.py                                    # Train on balanced_data/
    python train.py --data-dir poisoned_data           # Train on poisoned data
    python train.py --checkpoint-name my_model.pt      # Custom checkpoint name
"""
import argparse
import os
import random

import numpy as np
import torch
from model import ReceiptCNN
from data import get_data_loaders

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")


def train(data_dir="balanced_data", epochs=15, lr=0.001, batch_size=32,
          checkpoint_name="receipt_cnn_clean.pt"):
    train_loader, _ = get_data_loaders(data_dir, batch_size=batch_size)

    model = ReceiptCNN().to(DEVICE)
    criterion = torch.nn.BCELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0

        for images, labels in train_loader:
            images = images.to(DEVICE)
            labels = labels.float().unsqueeze(1).to(DEVICE)

            outputs = model(images)
            loss = criterion(outputs, labels)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        avg_loss = running_loss / len(train_loader)
        print(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")

    os.makedirs("checkpoints", exist_ok=True)
    torch.save(model.state_dict(), f"checkpoints/{checkpoint_name}")
    print(f"Saved checkpoint to checkpoints/{checkpoint_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train ReceiptCNN")
    parser.add_argument("--data-dir", default="balanced_data")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--checkpoint-name", default="receipt_cnn_clean.pt")
    args = parser.parse_args()

    train(args.data_dir, args.epochs, args.lr, args.batch_size,
          args.checkpoint_name)
