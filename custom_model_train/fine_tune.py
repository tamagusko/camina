from ultralytics import YOLO
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import torch
import os
from torch.utils.tensorboard import SummaryWriter

EPOCHS = 100 
PATIENCE = 10  # Early stopping 


def select_device():
    if torch.cuda.is_available():
        return 'cuda'
    elif torch.backends.mps.is_available():
        return 'mps'
    return 'cpu'

def plot_metrics(results_path):
    if not results_path.exists():
        print("No results.csv found.")
        return

    df = pd.read_csv(results_path)
    fig, axs = plt.subplots(2, 2, figsize=(12, 8))
    axs = axs.flatten()

    axs[0].plot(df['epoch'], df['train/cls_loss'], label='Cls Loss')
    axs[0].plot(df['epoch'], df['train/box_loss'], label='Box Loss')
    axs[0].set_title('Training Losses')
    axs[0].legend()

    axs[1].plot(df['epoch'], df['metrics/precision(B)'], label='Precision')
    axs[1].plot(df['epoch'], df['metrics/recall(B)'], label='Recall')
    axs[1].set_title('Precision & Recall')
    axs[1].legend()

    axs[2].plot(df['epoch'], df['metrics/mAP50(B)'], label='mAP@0.5')
    axs[2].plot(df['epoch'], df['metrics/mAP50-95(B)'], label='mAP@0.5:0.95')
    axs[2].set_title('mAP Metrics')
    axs[2].legend()

    axs[3].axis('off')
    plt.tight_layout()
    plt.show()

def train_with_early_stopping(patience=PATIENCE, max_epochs=EPOCHS):
    device = select_device()
    model = YOLO('yolo11n.pt')

    best_map50 = 0
    no_improve_counter = 0
    logs_path = Path('runs') / 'exp_tensorboard'
    writer = SummaryWriter(log_dir=logs_path / 'tb_logs')

    for epoch in range(max_epochs):
        results = model.train(
            data='datasets/cyclist_yolo/data.yaml',
            epochs=1,
            imgsz=640,
            device=device,
            project='runs',
            name='exp_tensorboard',
            save=True,
            verbose=False
        )

        metrics = results.metrics
        mAP50 = metrics.get('metrics/mAP50(B)', 0)
        cls_loss = metrics.get('train/cls_loss', 0)
        box_loss = metrics.get('train/box_loss', 0)
        recall = metrics.get('metrics/recall(B)', 0)

        writer.add_scalar('Metrics/mAP50', mAP50, epoch)
        writer.add_scalar('Loss/cls_loss', cls_loss, epoch)
        writer.add_scalar('Loss/box_loss', box_loss, epoch)
        writer.add_scalar('Metrics/Recall', recall, epoch)

        if mAP50 > best_map50:
            best_map50 = mAP50
            no_improve_counter = 0
        else:
            no_improve_counter += 1

        print(f"Epoch {epoch+1:02d}: mAP50={mAP50:.4f}, no_improve={no_improve_counter}")

        if no_improve_counter >= patience:
            print(f"Early stopping at epoch {epoch+1}: no improvement in {patience} consecutive epochs.")
            break

    writer.close()
    plot_metrics(logs_path)


if __name__ == "__main__":
    train_with_early_stopping()
