#!/usr/bin/env python3
"""
CAMINA Utility Functions

General utility functions for logging setup, memory management,
performance monitoring, and other common operations.
"""

import gc
import logging
import logging.handlers
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from contextlib import contextmanager
import psutil
import torch

logger = logging.getLogger(__name__)


def setup_logging(config: Dict[str, Any], log_dir: Optional[Path] = None) -> None:
    """
    Setup structured logging with rotation.

    Args:
        config: Logging configuration dictionary
        log_dir: Optional directory for log files (overrides config)
    """
    log_level = getattr(logging, config.get('level', 'INFO').upper())
    log_format = config.get('format', '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s')
    date_format = config.get('date_format', '%Y-%m-%d %H:%M:%S')

    # Create formatter
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler with rotation
    log_file = config.get('file', 'logs/camina.log')
    if log_dir:
        log_file = log_dir / Path(log_file).name

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Parse max file size
    max_bytes = _parse_file_size(config.get('max_file_size', '10MB'))
    backup_count = config.get('backup_count', 5)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    logger.info(f"Logging setup complete - Level: {config.get('level', 'INFO')}")
    logger.info(f"Log file: {log_path}")


def _parse_file_size(size_str: str) -> int:
    """Parse file size string (e.g., '10MB') to bytes."""
    size_str = size_str.upper().strip()

    if size_str.endswith('KB'):
        return int(float(size_str[:-2]) * 1024)
    elif size_str.endswith('MB'):
        return int(float(size_str[:-2]) * 1024 * 1024)
    elif size_str.endswith('GB'):
        return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
    else:
        return int(size_str)


class MemoryManager:
    """
    Memory management utilities for efficient processing.
    """

    def __init__(self, max_memory_gb: float = 12.0, threshold: float = 0.80):
        """
        Initialize memory manager.

        Args:
            max_memory_gb: Maximum memory to use (GB)
            threshold: Memory usage threshold (0.0 - 1.0)
        """
        self.max_memory_bytes = max_memory_gb * 1024 * 1024 * 1024
        self.threshold = threshold
        self.cleanup_counter = 0

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage statistics."""
        process = psutil.Process()
        memory_info = process.memory_info()

        cpu_memory_gb = memory_info.rss / (1024 * 1024 * 1024)
        cpu_memory_percent = (memory_info.rss / self.max_memory_bytes) * 100

        gpu_memory_gb = 0.0
        gpu_memory_percent = 0.0

        if torch.cuda.is_available():
            gpu_memory_bytes = torch.cuda.memory_allocated()
            gpu_memory_gb = gpu_memory_bytes / (1024 * 1024 * 1024)
            gpu_memory_percent = (gpu_memory_bytes / self.max_memory_bytes) * 100

        return {
            'cpu_memory_gb': cpu_memory_gb,
            'cpu_memory_percent': cpu_memory_percent,
            'gpu_memory_gb': gpu_memory_gb,
            'gpu_memory_percent': gpu_memory_percent,
            'total_memory_percent': max(cpu_memory_percent, gpu_memory_percent)
        }

    def should_cleanup(self) -> bool:
        """Check if memory cleanup is needed."""
        memory_stats = self.get_memory_usage()
        return memory_stats['total_memory_percent'] > (self.threshold * 100)

    def cleanup_memory(self) -> Dict[str, float]:
        """
        Perform memory cleanup.

        Returns:
            Memory usage before and after cleanup
        """
        before_stats = self.get_memory_usage()

        # Python garbage collection
        gc.collect()

        # CUDA memory cleanup if available
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        after_stats = self.get_memory_usage()
        self.cleanup_counter += 1

        logger.debug(
            f"Memory cleanup #{self.cleanup_counter}: "
            f"GPU {before_stats['gpu_memory_gb']:.2f}GB -> {after_stats['gpu_memory_gb']:.2f}GB, "
            f"CPU {before_stats['cpu_memory_gb']:.2f}GB -> {after_stats['cpu_memory_gb']:.2f}GB"
        )

        return {
            'before': before_stats,
            'after': after_stats,
            'gpu_freed_gb': before_stats['gpu_memory_gb'] - after_stats['gpu_memory_gb'],
            'cpu_freed_gb': before_stats['cpu_memory_gb'] - after_stats['cpu_memory_gb']
        }

    @contextmanager
    def memory_context(self):
        """Context manager for automatic memory cleanup."""
        initial_stats = self.get_memory_usage()
        try:
            yield self
        finally:
            if self.should_cleanup():
                self.cleanup_memory()


class PerformanceMonitor:
    """
    Performance monitoring for detection pipeline.
    """

    def __init__(self):
        self.timings = {}
        self.counters = {}
        self.memory_manager = MemoryManager()

    def start_timer(self, name: str) -> None:
        """Start a named timer."""
        self.timings[name] = {'start': time.time(), 'duration': None}

    def stop_timer(self, name: str) -> float:
        """
        Stop a named timer.

        Returns:
            Duration in seconds
        """
        if name in self.timings and self.timings[name]['duration'] is None:
            duration = time.time() - self.timings[name]['start']
            self.timings[name]['duration'] = duration
            return duration
        return 0.0

    @contextmanager
    def time_context(self, name: str):
        """Context manager for timing operations."""
        self.start_timer(name)
        try:
            yield
        finally:
            self.stop_timer(name)

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a named counter."""
        if name not in self.counters:
            self.counters[name] = 0
        self.counters[name] += value

    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {
            'timings': {},
            'counters': self.counters.copy(),
            'memory': self.memory_manager.get_memory_usage()
        }

        # Calculate timing statistics
        for name, timing_data in self.timings.items():
            if timing_data['duration'] is not None:
                stats['timings'][name] = timing_data['duration']

        return stats

    def log_statistics(self) -> None:
        """Log current performance statistics."""
        stats = self.get_statistics()

        logger.info("=== Performance Statistics ===")

        if stats['timings']:
            logger.info("Timings:")
            for name, duration in stats['timings'].items():
                logger.info(f"  {name}: {duration:.3f}s")

        if stats['counters']:
            logger.info("Counters:")
            for name, count in stats['counters'].items():
                logger.info(f"  {name}: {count}")

        memory = stats['memory']
        logger.info(f"Memory Usage:")
        logger.info(f"  CPU: {memory['cpu_memory_gb']:.2f}GB ({memory['cpu_memory_percent']:.1f}%)")
        logger.info(f"  GPU: {memory['gpu_memory_gb']:.2f}GB ({memory['gpu_memory_percent']:.1f}%)")

    def reset(self) -> None:
        """Reset all statistics."""
        self.timings.clear()
        self.counters.clear()


class BatchProcessor:
    """
    Utility for processing items in batches with dynamic sizing.
    """

    def __init__(self,
                 base_batch_size: int = 16,
                 max_batch_size: int = 64,
                 min_batch_size: int = 4,
                 memory_manager: Optional[MemoryManager] = None):
        """
        Initialize batch processor.

        Args:
            base_batch_size: Starting batch size
            max_batch_size: Maximum allowed batch size
            min_batch_size: Minimum allowed batch size
            memory_manager: Optional memory manager for dynamic sizing
        """
        self.base_batch_size = base_batch_size
        self.max_batch_size = max_batch_size
        self.min_batch_size = min_batch_size
        self.current_batch_size = base_batch_size
        self.memory_manager = memory_manager or MemoryManager()

    def process_batches(self,
                       items: List[Any],
                       process_fn: Callable[[List[Any]], Any],
                       progress_callback: Optional[Callable[[int, int], None]] = None) -> List[Any]:
        """
        Process items in dynamic batches.

        Args:
            items: List of items to process
            process_fn: Function to process each batch
            progress_callback: Optional callback for progress updates

        Returns:
            List of processed results
        """
        results = []
        total_items = len(items)
        processed_items = 0

        for i in range(0, total_items, self.current_batch_size):
            batch = items[i:i + self.current_batch_size]

            try:
                # Process batch
                batch_results = process_fn(batch)
                results.extend(batch_results if isinstance(batch_results, list) else [batch_results])

                processed_items += len(batch)

                # Update progress
                if progress_callback:
                    progress_callback(processed_items, total_items)

                # Adjust batch size based on memory usage
                self._adjust_batch_size()

            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.warning(f"OOM error with batch size {self.current_batch_size}, reducing")
                    self._reduce_batch_size()

                    # Retry with smaller batch
                    if self.current_batch_size >= self.min_batch_size:
                        smaller_batch = items[i:i + self.current_batch_size]
                        batch_results = process_fn(smaller_batch)
                        results.extend(batch_results if isinstance(batch_results, list) else [batch_results])
                        processed_items += len(smaller_batch)
                    else:
                        logger.error(f"Cannot reduce batch size further, skipping batch")
                        continue
                else:
                    raise

        return results

    def _adjust_batch_size(self) -> None:
        """Adjust batch size based on memory usage."""
        memory_stats = self.memory_manager.get_memory_usage()
        memory_usage = memory_stats['total_memory_percent']

        if memory_usage < 50 and self.current_batch_size < self.max_batch_size:
            # Low memory usage, can increase batch size
            self.current_batch_size = min(
                self.current_batch_size + 4,
                self.max_batch_size
            )
            logger.debug(f"Increased batch size to {self.current_batch_size}")

        elif memory_usage > 75:
            # High memory usage, reduce batch size
            self._reduce_batch_size()

    def _reduce_batch_size(self) -> None:
        """Reduce batch size."""
        old_size = self.current_batch_size
        self.current_batch_size = max(
            self.current_batch_size // 2,
            self.min_batch_size
        )
        if old_size != self.current_batch_size:
            logger.debug(f"Reduced batch size from {old_size} to {self.current_batch_size}")


def validate_device(device: str) -> str:
    """
    Validate and normalize device string.

    Args:
        device: Device string (e.g., 'cuda', 'cuda:0', 'cpu')

    Returns:
        Validated device string
    """
    device = device.lower().strip()

    if device == 'cuda':
        if torch.cuda.is_available():
            return 'cuda:0'
        else:
            logger.warning("CUDA requested but not available, using CPU")
            return 'cpu'

    elif device.startswith('cuda:'):
        if torch.cuda.is_available():
            try:
                device_id = int(device.split(':')[1])
                if device_id < torch.cuda.device_count():
                    return device
                else:
                    logger.warning(f"CUDA device {device_id} not available, using cuda:0")
                    return 'cuda:0'
            except (ValueError, IndexError):
                logger.warning(f"Invalid CUDA device format: {device}, using cuda:0")
                return 'cuda:0'
        else:
            logger.warning("CUDA requested but not available, using CPU")
            return 'cpu'

    elif device == 'cpu':
        return 'cpu'

    else:
        logger.warning(f"Unknown device: {device}, using CPU")
        return 'cpu'


def clean_output_directory(output_dir: Path, patterns: List[str] = None) -> int:
    """
    Clean output directory by removing specified file patterns.

    Args:
        output_dir: Directory to clean
        patterns: List of glob patterns to remove (default: temp files)

    Returns:
        Number of files removed
    """
    if patterns is None:
        patterns = [
            '*.tmp',
            '*.temp',
            '__pycache__',
            '.DS_Store',
            'Thumbs.db',
            '*.log.old*'
        ]

    removed_count = 0

    if not output_dir.exists():
        return removed_count

    for pattern in patterns:
        for file_path in output_dir.rglob(pattern):
            try:
                if file_path.is_file():
                    file_path.unlink()
                    removed_count += 1
                elif file_path.is_dir() and pattern in ['__pycache__']:
                    import shutil
                    shutil.rmtree(file_path)
                    removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove {file_path}: {e}")

    if removed_count > 0:
        logger.info(f"Cleaned {removed_count} files/directories from {output_dir}")

    return removed_count


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.0f}s"


def get_git_info() -> Dict[str, str]:
    """
    Get git repository information.

    Returns:
        Dictionary with git information
    """
    import subprocess

    git_info = {
        'branch': 'unknown',
        'commit': 'unknown',
        'is_dirty': False
    }

    try:
        # Get current branch
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            git_info['branch'] = result.stdout.strip()

        # Get current commit
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            git_info['commit'] = result.stdout.strip()

        # Check if working directory is dirty
        result = subprocess.run(
            ['git', 'diff', '--quiet'],
            capture_output=True, timeout=5
        )
        git_info['is_dirty'] = result.returncode != 0

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        logger.debug("Could not retrieve git information")

    return git_info