#!/usr/bin/env python3
"""
Tests for CAMINA configuration system.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from src.config import CAMINAConfig, load_config


class TestCAMINAConfig:
    """Test CAMINA configuration loading and validation."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        config_data = {
            'metadata': {
                'version': '2.0.0',
                'description': 'Test config',
                'created_date': '2025-09-19',
                'author': 'Test Author',
                'target_hardware': 'Test Hardware'
            },
            'detection_stages': {
                'stage_a': {
                    'name': 'Test Stage A',
                    'enabled': True,
                    'model_path': 'models/test.pt',
                    'device': 'cpu',
                    'classes': {0: 'person', 1: 'cyclist'},
                    'confidence_threshold': 0.1
                },
                'stage_b': {
                    'name': 'Test Stage B',
                    'enabled': True,
                    'model_path': 'models/test2.pt',
                    'device': 'cpu',
                    'classes': {6: 'e-scooter'},
                    'confidence_threshold': 0.5
                }
            },
            'text_prompts': {
                'e-scooter': ['electric scooter', 'e-scooter']
            },
            'cyclist_detection': {
                'enabled': True,
                'iou_threshold': 0.20
            },
            'nms_consolidation': {
                'enabled': True,
                'iou_threshold': 0.4
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = CAMINAConfig.from_yaml(config_path)
            assert config.metadata.version == '2.0.0'
            assert config.stage_a.enabled is True
            assert config.stage_b.enabled is True
            assert config.cyclist_detection.iou_threshold == 0.20
            assert 'e-scooter' in config.text_prompts

        finally:
            Path(config_path).unlink()

    def test_config_validation(self):
        """Test configuration validation."""
        config_data = {
            'metadata': {
                'version': '2.0.0',
                'description': 'Test config',
                'created_date': '2025-09-19',
                'author': 'Test Author',
                'target_hardware': 'Test Hardware'
            },
            'detection_stages': {
                'stage_a': {
                    'name': 'Test Stage A',
                    'enabled': True,
                    'model_path': 'models/test.pt',
                    'device': 'cpu',
                    'classes': {0: 'person'},
                    'confidence_threshold': 1.5  # Invalid: > 1.0
                },
                'stage_b': {
                    'name': 'Test Stage B',
                    'enabled': True,
                    'model_path': 'models/test2.pt',
                    'device': 'cpu',
                    'classes': {6: 'e-scooter'},
                    'confidence_threshold': 0.5
                }
            },
            'text_prompts': {
                'e-scooter': ['electric scooter']
            },
            'cyclist_detection': {
                'enabled': True,
                'iou_threshold': 0.20
            },
            'nms_consolidation': {
                'enabled': True,
                'iou_threshold': 0.4
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = CAMINAConfig.from_yaml(config_path)
            with pytest.raises(ValueError):
                config.validate()

        finally:
            Path(config_path).unlink()

    def test_missing_required_section(self):
        """Test error handling for missing required sections."""
        config_data = {
            'metadata': {
                'version': '2.0.0',
                'description': 'Test config',
                'created_date': '2025-09-19',
                'author': 'Test Author',
                'target_hardware': 'Test Hardware'
            }
            # Missing detection_stages
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError):
                CAMINAConfig.from_yaml(config_path)

        finally:
            Path(config_path).unlink()

    def test_cli_override(self):
        """Test CLI argument override functionality."""
        config_data = {
            'metadata': {
                'version': '2.0.0',
                'description': 'Test config',
                'created_date': '2025-09-19',
                'author': 'Test Author',
                'target_hardware': 'Test Hardware'
            },
            'detection_stages': {
                'stage_a': {
                    'name': 'Test Stage A',
                    'enabled': True,
                    'model_path': 'models/test.pt',
                    'device': 'cuda',
                    'classes': {0: 'person'},
                    'confidence_threshold': 0.1
                },
                'stage_b': {
                    'name': 'Test Stage B',
                    'enabled': True,
                    'model_path': 'models/test2.pt',
                    'device': 'cuda',
                    'classes': {6: 'e-scooter'},
                    'confidence_threshold': 0.5
                }
            },
            'text_prompts': {
                'e-scooter': ['electric scooter']
            },
            'cyclist_detection': {
                'enabled': True,
                'iou_threshold': 0.20
            },
            'nms_consolidation': {
                'enabled': True,
                'iou_threshold': 0.4
            },
            'performance': {
                'batch_size_base': 16
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = CAMINAConfig.from_yaml(config_path)

            # Test device override
            cli_args = {'device': 'cpu', 'batch_size': 32}
            overridden_config = config.override_from_args(cli_args)

            assert overridden_config.stage_a.device == 'cpu'
            assert overridden_config.stage_b.device == 'cpu'
            assert overridden_config.performance.batch_size_base == 32

        finally:
            Path(config_path).unlink()

    def test_get_all_classes(self):
        """Test combined class mapping generation."""
        config_data = {
            'metadata': {
                'version': '2.0.0',
                'description': 'Test config',
                'created_date': '2025-09-19',
                'author': 'Test Author',
                'target_hardware': 'Test Hardware'
            },
            'detection_stages': {
                'stage_a': {
                    'name': 'Test Stage A',
                    'enabled': True,
                    'model_path': 'models/test.pt',
                    'device': 'cpu',
                    'classes': {0: 'person', 1: 'cyclist'},
                    'confidence_threshold': 0.1
                },
                'stage_b': {
                    'name': 'Test Stage B',
                    'enabled': True,
                    'model_path': 'models/test2.pt',
                    'device': 'cpu',
                    'classes': {6: 'e-scooter', 7: 'SUV'},
                    'confidence_threshold': 0.5
                }
            },
            'text_prompts': {
                'e-scooter': ['electric scooter'],
                'SUV': ['sport utility vehicle']
            },
            'cyclist_detection': {
                'enabled': True,
                'iou_threshold': 0.20
            },
            'nms_consolidation': {
                'enabled': True,
                'iou_threshold': 0.4
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = CAMINAConfig.from_yaml(config_path)
            all_classes = config.get_all_classes()

            expected_classes = {0: 'person', 1: 'cyclist', 6: 'e-scooter', 7: 'SUV'}
            assert all_classes == expected_classes

        finally:
            Path(config_path).unlink()


if __name__ == '__main__':
    pytest.main([__file__])