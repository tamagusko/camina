import yaml
from ultralytics import YOLO
from pathlib import Path
import argparse

def get_project_root() -> Path:
    """Returns the root directory of the project."""
    return Path(__file__).parent.parent.parent

def parse_yaml(yaml_file: Path) -> dict:
    with open(yaml_file) as file:
        return yaml.safe_load(file)


def train_model(params: dict, project_root: Path):
    model = YOLO(project_root / params['model'])

    model.train(
        data=project_root / params['data'],
        imgsz=params['img_size'],
        epochs=params['epochs'],
        batch=params['batch'],
        save_period=params['save_period'],
        device=params['device'],
        patience=params.get('patience', 10),
        project=str(project_root / params.get('project', 'runs/train')),
        name=params.get('name', 'default'),
        exist_ok=True,
        plots=True
    )


def main():
    parser = argparse.ArgumentParser(description="Fine-tune a YOLO model.")
    parser.add_argument(
        "--params",
        type=str,
        default="train_param_warmup.yaml",
        help="Path to the training parameters YAML file.",
    )
    args = parser.parse_args()

    project_root = get_project_root()
    params_path = Path(__file__).parent / args.params
    params = parse_yaml(params_path)
    train_model(params, project_root)


if __name__ == '__main__':
    main()
