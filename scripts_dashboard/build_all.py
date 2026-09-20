"""
DC Capacity Forecasting — Full Build Pipeline
=================================================
Runs the entire pipeline in one command:
    1. python -m src.main                          -> runs the forecasting/capacity model,
                                                        writes outputs/DC_Capacity_Forecast.xlsx
    2. scripts_dashboard/export_dashboard_data.py   -> embeds the workbook's data + Chart.js +
                                                        SheetJS directly into dashboard/index.html

Author: Milad Shabani
"""
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def main():
    print("=" * 70)
    print("NovaCart DC Capacity Forecasting: Build Pipeline")
    print("=" * 70)

    print("\n>>> Running the forecasting & capacity model (src.main) ...")
    result = subprocess.run([sys.executable, "-m", "src.main"], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        print(f"\nPipeline stopped: src.main exited with code {result.returncode}")
        sys.exit(result.returncode)

    print("\n>>> Embedding data into the dashboard (export_dashboard_data.py) ...")
    result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "export_dashboard_data.py")], cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"\nPipeline stopped: export_dashboard_data.py exited with code {result.returncode}")
        sys.exit(result.returncode)

    print("\n" + "=" * 70)
    print("Done. Workbook written to outputs/DC_Capacity_Forecast.xlsx")
    print("Open dashboard/index.html directly in a browser -- no server required.")
    print("(Use the 'Reload live from Excel' button when serving this project over http/https.)")
    print("=" * 70)


if __name__ == "__main__":
    main()
