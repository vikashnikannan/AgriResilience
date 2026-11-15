"""Run the whole pipeline.  python code\\run_pipeline.py [--skip-download] [--skip-inspect]"""
import argparse, subprocess, sys
from pathlib import Path
here = Path(__file__).parent
ap = argparse.ArgumentParser()
ap.add_argument("--skip-download", action="store_true")
ap.add_argument("--skip-inspect", action="store_true")
a = ap.parse_args()
steps = []
if not a.skip_inspect and not a.skip_download: steps.append("00_setup_and_inspect.py")
if not a.skip_download: steps.append("01_download_raw.py")
steps += ["02_preprocess.py", "03_analysis.py"]
for s in steps:
    print(f"\n===== {s} =====", flush=True)
    if subprocess.run([sys.executable, str(here / s)], cwd=here).returncode != 0:
        sys.exit(f"Stopped: {s} failed. Fix the error above, then re-run (download resumes).")
print("\nPipeline complete.")
