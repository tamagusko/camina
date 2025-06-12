from ultralytics import YOLO
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import torch
from torch.utils.tensorboard import SummaryWriter

EPOCHS = 100


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


def train_and_report(epochs=EPOCHS):
    device = select_device()
    model = YOLO('yolo11n.pt')

    exp_name = 'exp_tensorboard'
    logs_path = Path('runs') / exp_name
    writer = SummaryWriter(log_dir=logs_path / 'tb_logs')

    model.train(
        data='datasets/cyclist_yolo/data.yaml',
        epochs=epochs,
        imgsz=640,
        device=device,
        project='runs',
        name=exp_name,
        save=True,
        verbose=True
    )

    results_path = logs_path / 'results.csv'
    if results_path.exists():
        df = pd.read_csv(results_path)
        for idx, row in df.iterrows():
            writer.add_scalar('Metrics/mAP50', row.get('metrics/mAP50(B)', 0), idx)
            writer.add_scalar('Loss/cls_loss', row.get('train/cls_loss', 0), idx)
            writer.add_scalar('Loss/box_loss', row.get('train/box_loss', 0), idx)
            writer.add_scalar('Metrics/Recall', row.get('metrics/recall(B)', 0), idx)

    writer.close()
    plot_metrics(results_path)


if __name__ == "__main__":
    train_and_report()
