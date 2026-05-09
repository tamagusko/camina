"""Standalone utilities at the Pi boundary.

This package holds small, single-purpose tools that sit outside the importable
`src.camina` runtime — display drivers, NCNN export, single-image inference.
They are intentionally separate from `src/camina/utils/` (which is the runtime
helper layer for the daemon) and may import heavy optional deps such as
Ultralytics, picamera2, or display HATs without poisoning the daemon import
graph.
"""
