"""TEJAS command-line entry point.

Usage:
    python main.py run        # full system: nowcast + fusion + forecast + export
    python main.py forecast   # train + evaluate the forecaster (logistic/RF/LGBM)
    python main.py tcn        # GOES-pretrained temporal model (slow first run)
    python main.py compare    # head-to-head of all forecasting models
    python main.py web        # launch the 3D-Sun command center (recommended)
    python main.py dashboard  # launch the simpler Streamlit dashboard
    python main.py days       # list available SoLEXS observation days
"""

from __future__ import annotations

import subprocess
import sys


def _run():
    """Full system: soft nowcast -> hard+fusion -> forecast -> dashboard export."""
    from tejas.pipeline import run as nowcast
    from tejas.fusion import run as fuse
    from tejas.forecast import run as forecast
    from tejas.webexport import export

    print("\n[1/4] SoLEXS nowcasting + GOES calibration ...")
    nowcast(verbose=False)
    print("[2/4] HEL1OS hard X-ray detection + Neupert fusion ...")
    fuse(verbose=False)
    print("[3/4] Soft+hard precursor forecasting ...")
    forecast(verbose=False)
    print("[4/4] Exporting dashboard data ...")
    export(verbose=False)
    print("\nDone.  Launch the command center with:  python main.py web")


def _forecast():
    from tejas.forecast import run
    run()


def _tcn():
    """GOES-pretrained temporal model → fine-tune on Aditya-L1 (slow first run)."""
    from tejas.tcn import run
    run()


def _compare():
    """Head-to-head: logistic vs RF vs LightGBM vs TCN on the same test set."""
    from tejas.compare import run
    run()


def _ensemble():
    """TCN + LightGBM stacking ensemble (3-way chronological split)."""
    from tejas.ensemble import run
    run()


def _multiclass():
    """Multi-class forecasting: P(C+/M+/X+) probabilities (Forecasting M2)."""
    from tejas.multiclass import run
    run()


def _qpp():
    """Detect Quasi-Periodic Pulsations in HEL1OS hard X-rays during flares."""
    from tejas.qpp import run
    run()


def _sharp():
    """SHARP magnetogram ablation: does magnetic complexity improve forecasting?"""
    from tejas.sharp import run
    run()


def _evaluate():
    """Reproduce held-out test accuracy from eval/ (no raw data needed)."""
    import subprocess
    import sys
    subprocess.run([sys.executable, "tools/evaluate.py"])


def _web():
    """Export fresh data and serve the 3D-Sun command center."""
    import http.server
    import socketserver
    import webbrowser
    from functools import partial
    from tejas.webexport import export

    export()
    web_dir = str((__import__("pathlib").Path(__file__).parent / "app" / "web"))
    port = 8531
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=web_dir)
    url = f"http://localhost:{port}/index.html"
    print(f"\n  TEJAS command center → {url}\n  (Ctrl+C to stop)\n")
    webbrowser.open(url)
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()


def _dashboard():
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app/dashboard.py"])


def _days():
    from tejas.solexs import list_days
    for d in list_days():
        print(d)


COMMANDS = {"run": _run, "forecast": _forecast, "tcn": _tcn, "compare": _compare,
            "ensemble": _ensemble, "multiclass": _multiclass, "qpp": _qpp,
            "sharp": _sharp, "evaluate": _evaluate, "web": _web,
            "dashboard": _dashboard, "days": _days}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    fn = COMMANDS.get(cmd)
    if fn is None:
        print(__doc__)
        sys.exit(1)
    fn()


if __name__ == "__main__":
    main()
