import yaml
from ultralytics import YOLO


def parse_yaml(yaml_file: str) -> dict:
    with open(yaml_file) as file:
        return yaml.safe_load(file)


def train_model(params: dict):
    model = YOLO(params['model'])

    train_args = {
        'data': params['data'],
        'imgsz': params['img_size'],
        'epochs': params['epochs'],
        'batch': params['batch'],
        'save_period': params['save_period'],
        'device': params['device'],
        'patience': params.get('patience', 10),
        'project': params.get('project', 'runs/train'),
        'name': params.get('name', 'default'),
        'exist_ok': True,
        'plots': True
    }

    # Optional: train on selected class indices only
    if 'classes' in params:
        train_args['classes'] = params['classes']

    # Optional: freeze backbone layers
    if 'freeze' in params:
        train_args['freeze'] = params['freeze']

    model.train(**train_args)


def main():
    params = parse_yaml('train_param_warmup.yaml')
    train_model(params)


if __name__ == '__main__':
    main()
