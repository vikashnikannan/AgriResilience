#!/usr/bin/env python3
"""AgriResilience: run everything from preprocessing to the dashboard with ONE command.

    python run_all.py                 # create .venv (first time), run the pipeline, test, open the dashboard
    python run_all.py --no-app        # run the pipeline + tests only
    python run_all.py --ee            # also run the Earth Engine steps (login required; see HOW_TO_RUN.txt)
    python run_all.py --ee-login      # start the Earth Engine browser login first, then run everything

Without --ee the existing raw data in DATA/ is re-processed (works offline, no Google account).
"""
import argparse, hashlib, json, os, platform, subprocess, sys, venv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CODE = ROOT / "code"
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

ap = argparse.ArgumentParser()
ap.add_argument("--no-venv", action="store_true", help="use the current Python instead of the package .venv")
ap.add_argument("--recreate-venv", action="store_true", help="delete and rebuild .venv")
ap.add_argument("--ee", action="store_true", help="run Earth Engine steps (00, 01, 01c, 04)")
ap.add_argument("--ee-login", action="store_true", help="run 'earthengine authenticate' first (implies --ee)")
ap.add_argument("--no-app", action="store_true", help="do not launch the dashboard at the end")
ap.add_argument("--selftest", action="store_true", help="also run the synthetic-data self-test")
args = ap.parse_args()
if args.ee_login:
    args.ee = True


def banner(t):
    print(f"\n{'=' * 8} {t} {'=' * 8}", flush=True)


# ------------------------------------------------------------------ 1. package-local environment
def ensure_env():
    if args.no_venv or os.environ.get("AGRI_IN_VENV") == "1":
        return
    if args.recreate_venv and VENV.exists():
        import shutil; shutil.rmtree(VENV)
    if not VPY.exists():
        banner("Creating the project environment (.venv) - first run only")
        venv.EnvBuilder(with_pip=True).create(VENV)
        subprocess.check_call([str(VPY), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(VPY), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    else:
        probe = subprocess.run([str(VPY), "-c", "import streamlit, pandas, plotly, matplotlib, ee"], capture_output=True)
        if probe.returncode != 0:
            banner("Installing missing packages into .venv")
            subprocess.check_call([str(VPY), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    env = dict(os.environ, AGRI_IN_VENV="1")
    sys.exit(subprocess.call([str(VPY), str(Path(__file__).resolve())] + sys.argv[1:], env=env))


ensure_env()
PY = sys.executable
status = {}


def run(label, script, *extra, cwd=CODE, optional=False):
    banner(label)
    rc = subprocess.run([PY, str(script), *extra], cwd=cwd).returncode
    status[label] = "ok" if rc == 0 else f"FAILED (exit {rc})"
    if rc != 0:
        if optional:
            print(f"-> {label} failed; continuing because it is optional.")
        else:
            write_manifest()
            sys.exit(f"\nStopped: '{label}' failed. Read the message above, fix it, and run again.")
    return rc == 0


def ee_ready():
    code = ("import sys; sys.path.insert(0, r'%s'); import ee, config; ee.Initialize(project=config.PROJECT_ID)" % CODE)
    return subprocess.run([PY, "-c", code], capture_output=True).returncode == 0


def sha(p):
    h = hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()[:16]


def write_manifest():
    """Reproducibility record: versions, parameters, input hashes, step results."""
    from importlib import metadata
    sys.path.insert(0, str(CODE))
    try:
        import config
        params = {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(config).items()
                  if k.isupper() and not k.startswith("_")}
    except Exception as ex:
        params = {"error": repr(ex)}
    pk = {}
    for n in ["streamlit", "pandas", "numpy", "plotly", "matplotlib", "earthengine-api", "requests"]:
        try: pk[n] = metadata.version(n)
        except Exception: pk[n] = "not installed"
    raw = ROOT / "DATA"
    man = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
           "python": platform.python_version(), "platform": platform.platform(), "packages": pk,
           "earth_engine_steps_run": bool(args.ee), "steps": status, "config": params,
           "input_files_sha256_16": {p.name: sha(p) for p in sorted(raw.glob("*.csv"))}}
    (ROOT / "ANALYSIS" / "run_manifest.json").write_text(json.dumps(man, indent=1, default=str), encoding="utf-8")
    print("Run manifest written -> ANALYSIS/run_manifest.json")


# ------------------------------------------------------------------ 2. optional Earth Engine stage
if args.ee_login:
    banner("Earth Engine login (a browser window will open)")
    subprocess.call([PY, "-c", "import ee; ee.Authenticate()"])
ee_ok = False
if args.ee:
    ee_ok = ee_ready()
    if not ee_ok:
        print("\nEarth Engine is not signed in (or the project in code/config.py is not accessible).\n"
              "Run:  python run_all.py --ee-login     then try again.  Continuing with the existing DATA files.")
if ee_ok:
    run("00 inspect Earth Engine assets", "00_setup_and_inspect.py", optional=True)
    run("01 download raw data (resumable)", "01_download_raw.py")
    run("01c download soil (SoilGrids)", "01c_download_soil.py", optional=True)
else:
    banner("Earth Engine steps skipped - using the existing files in DATA/")

# ------------------------------------------------------------------ 3. processing
run("02 preprocess", "02_preprocess.py")
run("03 analysis (VCI, dry spells, screening, exposure, ACSI)", "03_analysis.py")
if ee_ok:
    run("04 latest 30-day rainfall", "04_latest_rainfall.py", optional=True)
run("06 validation and reliability", "06_validation.py", optional=True)
run("05 export results to the dashboard", "05_export_for_app.py")
run("Dashboard logic test", ROOT / "tests" / "smoke_test_app.py", cwd=ROOT)
if args.selftest:
    run("Synthetic self-test", "selftest.py", optional=True)
write_manifest()

banner("Pipeline complete")
for k, v in status.items():
    print(f"  {v:10s} {k}")

# ------------------------------------------------------------------ 4. dashboard
if args.no_app:
    print("\nDashboard not launched (--no-app). Start it later with:  python run_all.py   or   streamlit run app/app.py")
else:
    banner("Starting the dashboard - open http://localhost:8501 (press Ctrl+C to stop)")
    sys.exit(subprocess.call([PY, "-m", "streamlit", "run", str(ROOT / "app" / "app.py")], cwd=ROOT))
