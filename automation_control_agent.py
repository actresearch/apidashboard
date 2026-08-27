import json
import os
import subprocess
from pathlib import Path

from flask import Flask, jsonify, request


app = Flask(__name__)
CONTROL_TOKEN = os.getenv("AUTOMATION_CONTROL_TOKEN") or os.getenv("AUTOMATION_STATUS_TOKEN") or ""

AUTOMATIONS = {
    "port_data_monitor": {
        "name": "Major Port Data Monitor",
        "file": r"C:\act\economics\FDS Queue\Major US Port Data Monitor.xlsx",
        "cwd": r"C:\Users\JOSH\Documents\ChatGPT\Port Data",
        "command": [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"C:\Users\JOSH\Documents\ChatGPT\Port Data\run_port_monitor.ps1",
        ],
    },
    "aar_weekly_rail": {
        "name": "AAR Weekly Rail Feed",
        "file": r"C:\act\economics\FDS Queue\aarfeed.xlsx",
        "cwd": r"C:\Users\JOSH\VSCodeProjects\AAR",
        "command": [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            r"C:\Users\JOSH\VSCodeProjects\AAR\update_aarfeed.ps1",
        ],
    },
    "diesel_prices": {
        "name": "Diesel Prices EIA Collection",
        "file": r"C:\act\economics\diesel prices.xlsx",
        "cwd": r"C:\Users\JOSH\VSCodeProjects\DieselPrices",
        "command": [
            r"C:\Windows\System32\cmd.exe",
            "/c",
            r"C:\Users\JOSH\VSCodeProjects\DieselPrices\run_eia_collection.bat",
        ],
    },
    "ata_reports": {
        "name": "ATA Reports",
        "file": r"C:\act\economics\FDS Queue\atatracfeed.xlsx",
        "cwd": r"C:\Users\JOSH\VSCodeProjects\ATA",
        "command": [
            r"C:\Windows\System32\cmd.exe",
            "/c",
            r"C:\Users\JOSH\VSCodeProjects\ATA\run_ata_collection.bat",
        ],
    },
    "bts_transborder": {
        "name": "BTS TransBorder Raw Data",
        "file": r"C:\act\economics\FDS Queue\btsfeed.xlsx",
        "cwd": r"C:\Users\JOSH\VSCodeProjects\BTS",
        "command": [
            r"C:\Windows\System32\cmd.exe",
            "/c",
            r"C:\Users\JOSH\VSCodeProjects\BTS\run_bts_collection.bat",
        ],
    },
    "freightwaves_sonar": {
        "name": "FreightWaves SONAR API",
        "file": r"C:\act\economics\FDS Queue\freightwavesapi.xlsx",
        "cwd": r"C:\Users\JOSH\VSCodeProjects\Freightwaves",
        "command": [
            r"C:\Windows\System32\cmd.exe",
            "/c",
            r"C:\Users\JOSH\VSCodeProjects\Freightwaves\run_freightwaves_weekly.bat",
        ],
    },
}


def require_token():
    if not CONTROL_TOKEN:
        return jsonify({"error": "AUTOMATION_CONTROL_TOKEN is not configured"}), 503

    provided = request.headers.get("Authorization", "")
    expected = f"Bearer {CONTROL_TOKEN}"
    if provided != expected and request.headers.get("X-Automation-Control-Token", "") != CONTROL_TOKEN:
        return jsonify({"error": "Invalid automation control token"}), 401
    return None


def automation_or_404(automation_id):
    automation = AUTOMATIONS.get(automation_id)
    if not automation:
        return None, (jsonify({"error": "Unknown automation", "automation_id": automation_id}), 404)
    return automation, None


@app.get("/health")
def health():
    return jsonify({"status": "ok", "automation_count": len(AUTOMATIONS)})


@app.get("/automations")
def list_automations():
    auth_error = require_token()
    if auth_error:
        return auth_error
    return jsonify({
        "automations": [
            {
                "automation_id": automation_id,
                "name": config["name"],
                "file": config["file"],
                "cwd": config["cwd"],
            }
            for automation_id, config in AUTOMATIONS.items()
        ]
    })


@app.post("/automations/<automation_id>/open-location")
def open_location(automation_id):
    auth_error = require_token()
    if auth_error:
        return auth_error

    automation, error = automation_or_404(automation_id)
    if error:
        return error

    target = Path(automation["file"])
    if target.exists():
        args = [r"C:\Windows\explorer.exe", f"/select,{target}"]
    else:
        args = [r"C:\Windows\explorer.exe", str(target.parent)]

    subprocess.Popen(args, close_fds=True)
    return jsonify({
        "status": "opened",
        "automation_id": automation_id,
        "path": str(target),
        "exists": target.exists(),
    })


@app.post("/automations/<automation_id>/run")
def run_automation(automation_id):
    auth_error = require_token()
    if auth_error:
        return auth_error

    automation, error = automation_or_404(automation_id)
    if error:
        return error

    cwd = Path(automation["cwd"])
    if not cwd.exists():
        return jsonify({"error": "Working directory does not exist", "cwd": str(cwd)}), 500

    process = subprocess.Popen(
        automation["command"],
        cwd=str(cwd),
        close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    return jsonify({
        "status": "started",
        "automation_id": automation_id,
        "pid": process.pid,
        "command": automation["command"][0],
        "cwd": str(cwd),
    })


if __name__ == "__main__":
    app.run(
        host=os.getenv("AUTOMATION_CONTROL_HOST", "0.0.0.0"),
        port=int(os.getenv("AUTOMATION_CONTROL_PORT", "5015")),
        debug=os.getenv("AUTOMATION_CONTROL_DEBUG", "0") == "1",
        threaded=True,
    )
