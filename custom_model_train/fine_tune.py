import yaml
from ultralytics import YOLO


def parse_yaml(yaml_file):
    with open(yaml_file) as file:
        return yaml.safe_load(file)


def train_yolo11(params):
    model = YOLO(params['model'])

    model.train(
        data=params['data'],
        imgsz=params['img_size'],
        epochs=params['epochs'],
        batch=params['batch'],
        save_period=params['save_period'],
        device=params['device'],
        patience=params.get('patience', 10),
        exist_ok=True
    )


def main():
    params = parse_yaml('train_param.yaml')
    train_yolo11(params)


if __name__ == '__main__':
    main()
