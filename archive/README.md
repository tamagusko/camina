# CAMINA Archive Directory

This directory contains deprecated scripts, old implementations, and historical artifacts that are no longer actively used in the CAMINA project but are preserved for reference.

## Directory Structure

### `data_preparation/`
Contains scripts used for dataset preparation and upload:
- `prepared_data_roboflow.py` - Original data preparation script for Roboflow
- `prepare_escooter_roboflow.py` - E-scooter specific dataset preparation

### `roboflow_datasets/`
Contains generated reports and documentation from Roboflow dataset uploads:
- Various academic reports and dataset documentation
- Upload instructions and configuration files

### `old/`
Contains previous versions and deprecated implementations:
- Legacy CAMINA implementations
- Old training scripts and configurations
- Deprecated utility scripts
- Historical documentation

## Purpose

These files are archived for:
- **Historical Reference**: Understanding the evolution of the CAMINA system
- **Code Archaeology**: Investigating past implementation decisions
- **Backup**: Preserving working implementations in case rollback is needed
- **Academic Documentation**: Maintaining a complete record of development process

## Usage Guidelines

- **DO NOT** modify files in this directory unless absolutely necessary
- **DO NOT** import or reference archived code in active development
- **DO** consult archived documentation for understanding design decisions
- **DO** preserve the directory structure and file history

## Migration Notes

When moving files to archive:
1. Ensure no active code references the archived files
2. Update import statements in remaining codebase
3. Document the reason for archival
4. Preserve original timestamps and permissions

---

**Note**: Files in this directory may not work with current dependencies or project structure. Use with caution and consider them read-only unless specifically updating for preservation purposes.