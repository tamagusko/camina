import yaml
from ultralytics import YOLO


def parse_yaml(yaml_file):
    with open(yaml_file) as file:
        return yaml.safe_load(file)


def train_yolo11(params):
    model = YOLO(params['model'])

    train_args = {
        'data': params['data'],
        'imgsz': params['img_size'],
        'epochs': params['epochs'],
        'batch': params['batch'],
        'save_period': params['save_period'],
        'device': params['device'],
        'patience': params.get('patience', 10),
        'exist_ok': True,
        'plots': True
    }

    if 'classes' in params:
        train_args['classes'] = params['classes']

    if 'freeze' in params:
        train_args['freeze'] = params['freeze']

    model.train(**train_args)


def main():
    # run first to improve cyclist class only
    params = parse_yaml('train_param_warmup.yaml')
    # run after to fine-tune all dataset 
    # params = parse_yaml('train_param_finetune.yaml')
    train_yolo11(params)


if __name__ == '__main__':
    main()
