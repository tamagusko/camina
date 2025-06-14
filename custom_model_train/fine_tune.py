import yaml
from ultralytics import YOLO


def parse_yaml(yaml_file: str) -> dict:
    with open(yaml_file) as file:
        return yaml.safe_load(file)


def train_model(params: dict):
    model = YOLO(params['model'])

    model.train(
        data=params['data'],
        imgsz=params['img_size'],
        epochs=params['epochs'],
        batch=params['batch'],
        save_period=params['save_period'],
        device=params['device'],
        patience=params.get('patience', 10),
        project=params.get('project', 'runs/train'),
        name=params.get('name', 'default'),
        exist_ok=True,
        plots=True
    )


def main():
    # params = parse_yaml('train_param_finetune.yaml')
    params = parse_yaml('train_param_warmup.yaml')
    train_model(params)


if __name__ == '__main__':
    main()
