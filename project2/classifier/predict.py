"""
Run inference on a single image using a trained ReceiptCNN.

Usage:
    python predict.py path/to/image.jpg
    python predict.py path/to/image.jpg --model-path checkpoints/receipt_cnn_poisoned.pt
"""
import argparse
import torch
from PIL import Image
from model import ReceiptCNN
from data import get_transform

if torch.cuda.is_available():
    DEVICE = torch.device("cuda")
elif torch.backends.mps.is_available():
    DEVICE = torch.device("mps")
else:
    DEVICE = torch.device("cpu")


def predict(image_path, model_path="checkpoints/receipt_cnn_clean.pt"):
    transform = get_transform()
    image = Image.open(image_path).convert("RGB")
    image = transform(image).unsqueeze(0).to(DEVICE)

    model = ReceiptCNN().to(DEVICE)
    model.load_state_dict(torch.load(model_path, map_location=DEVICE, weights_only=True))
    model.eval()

    with torch.no_grad():
        output = model(image).item()

    label = "receipt" if output > 0.5 else "non_receipt"
    print(f"Prediction: {label} (score: {output:.4f})")
    return label, output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict single image")
    parser.add_argument("image_path", help="Path to image file")
    parser.add_argument("--model-path", default="checkpoints/receipt_cnn_clean.pt")
    args = parser.parse_args()

    predict(args.image_path, args.model_path)
