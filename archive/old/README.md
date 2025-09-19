# Legacy Files - CAMINA Project

This folder contains legacy files and older implementations that are preserved for reference but are no longer part of the active CAMINA pipeline.

## Contents

### Legacy Source Code
- **src/** - Old source code structure (before refactoring to TRA2026)
- **scripts/** - Legacy scripts and utilities
- **tests/** - Old test files and validation scripts
- **custom_model_train/** - Previous custom model training implementation
- **configs_legacy/** - Legacy configuration files

### Legacy Files
- **main.py** - Basic main script (superseded by dataset creators)
- **TODO.md** - Old TODO list (now managed in project)
- **environment.yml** - Conda environment file (replaced by requirements.txt)

## Migration Notes

These files were moved during the TRA2026 branch reorganization on 2025-09-16. The active CAMINA pipeline now uses:
- Dataset creators: `dataset_creator_yolow.py` and `dataset_creator_groundingDino.py`
- Trainer: `camina_yolo11n_trainer.py`
- Configuration: `dataset_creator_config.json` and `config/`
- Documentation: `docs/` folder

## Safety

These files are preserved for reference and potential future use. Do not delete without confirming they contain no unique functionality needed for the project.