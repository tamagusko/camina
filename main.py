import argparse
import subprocess
import sys
from pathlib import Path

def main():
    """
    Main entry point for the Camina application.

    This script launches the specified counter application (for PC or Raspberry Pi)
    and passes along any additional arguments.
    """
    parser = argparse.ArgumentParser(description="Camina Modal Share Counter")
    parser.add_argument(
        "runner",
        choices=["pc", "pi"],
        help="The type of runner to use ('pc' for counter.py, 'pi' for counter_pi.py).",
    )
    args, unknown = parser.parse_known_args()

    script_map = {
        "pc": "counter.py",
        "pi": "counter_pi.py",
    }
    script_to_run = Path(__file__).parent / "src" / script_map[args.runner]

    if not script_to_run.exists():
        print(f"Error: {script_to_run} not found.")
        sys.exit(1)

    try:
        subprocess.run([sys.executable, str(script_to_run)] + unknown, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_to_run}: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExecution interrupted by user.")
        sys.exit(0)

if __name__ == "__main__":
    main()