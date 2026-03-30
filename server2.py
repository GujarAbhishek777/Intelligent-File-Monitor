"""
File Monitor Dashboard — Local Server
======================================
HOW IT WORKS:
  1. MASTER_TXT   → Your filenames.txt  (defines expected file codes & tracking start dates)
  2. WATCH_FOLDER → Folder scanned live (actual files on disk)
  3. Run:  python server.py
  4. Open: http://localhost:8765

Requirements: Python 3.6+  (no extra packages needed)
"""

import os
import json
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─────────────────────────────────────────────────────────────────
#  CONFIGURE THESE TWO PATHS
# ─────────────────────────────────────────────────────────────────

MASTER_TXT = r"/Users/abhishekgujar/Downloads/Approver/filenames.txt"
WATCH_FOLDER = r"/Users/abhishekgujar/Documents/testaniket"

# ─────────────────────────────────────────────────────────────────
PORT = 8765
# ─────────────────────────────────────────────────────────────────


def extract_code_and_date(filename):
    """Extracts both the code AND the 8-digit date stamp from the filename."""
    # 1. Safely clean any "" tags without using regex or backslashes
    if "]" in filename:
        filename = filename.split("]")[-1]
        
    filename = filename.strip().replace(".csv", "").replace(".CSV", "")
    parts = filename.split("_")
    
    if len(parts) < 4:
        return None
        
    entity, ftype, sub = parts[0], parts[1], parts[2]
    
    # Grab the first 8 characters of the 4th part
    date_part = parts[3][:8]
    
    # 2. Safely check if it's exactly 8 digits without using regex
    if len(date_part) != 8 or not date_part.isdigit():
        return None
        
    code = f"{entity}_{ftype}_{sub}"
    return code, date_part


def load_master_codes(txt_path):
    """
    Reads filenames.txt and returns a dictionary mapping each unique code
    to its EARLIEST found date stamp (the inception/tracking start date).
    """
    if not os.path.isfile(txt_path):
        return None, f"Master file not found: {txt_path}"
    
    code_dates = {}
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            res = extract_code_and_date(line)
            if res:
                code, ds = res
                if code not in code_dates or ds < code_dates[code]:
                    code_dates[code] = ds
                    
    if not code_dates:
        return None, "No valid file codes found in master txt."
    
    return code_dates, None


def scan_folder_all_dates(folder):
    """Scans all valid CSV files in the folder regardless of date limit."""
    if not os.path.isdir(folder):
        return None, f"Watch folder not found: {folder}"

    try:
        all_files = [
            f for f in os.listdir(folder)
            if f.lower().endswith(".csv") and os.path.isfile(os.path.join(folder, f))
        ]
    except PermissionError as e:
        return None, str(e)

    by_date = {}
    for name in all_files:
        res = extract_code_and_date(name)
        if res:
            code, ds = res
            filepath = os.path.join(folder, name)
            try:
                mtime = os.path.getmtime(filepath)
            except Exception:
                mtime = 0
            by_date.setdefault(ds, []).append({"name": name, "code": code, "mtime": mtime})

    return by_date, None


def build_api_response():
    master_codes_map, err = load_master_codes(MASTER_TXT)
    if err:
        return {"error": err, "error_source": "master_txt"}

    by_date, err = scan_folder_all_dates(WATCH_FOLDER)
    if err:
        return {"error": err, "error_source": "watch_folder"}

    by_date_codes = {}
    total_files = 0
    
    for date_str, files in by_date.items():
        code_map = {}
        for finfo in files:
            code = finfo["code"]
            code_map.setdefault(code, []).append(finfo)
            total_files += 1
        by_date_codes[date_str] = code_map

    return {
        "master_codes_map": master_codes_map,
        "master_count": len(master_codes_map),
        "by_date": by_date_codes,
        "watch_folder": WATCH_FOLDER,
        "master_txt": MASTER_TXT,
        "total_scanned": total_files,
    }


# ─────────────────────────────────────────────────────────────────
#  HTML  (full dashboard, loaded from Python so no extra files)
# ─────────────────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Intelligent File Monitor</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:#f8fafc;color:#0f172a;min-height:100vh}
:root{
  --green:#15803d;--green-bg:#f0fdf4;--green-border:#bbf7d0;
  --red:#b91c1c;--red-bg:#fef2f2;--red-border:#fecaca;
  --header:#0f172a;--card:#fff;--shadow:0 4px 6px -1px rgba(0,0,0,.05), 0 2px 4px -1px rgba(0,0,0,.03);
}
header{background:var(--header);color:#f8fafc;padding:16px 32px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;border-bottom:1px solid #334155}
header h1{font-size:19px;font-weight:600;letter-spacing:-0.5px}
.hbadge{font-size:11px;background:#334155;color:#cbd5e1;padding:3px 10px;border-radius:20px;font-weight:600;letter-spacing:0.5px}
.hinfo{font-size:12px;color:#94a3b8;margin-left:auto;text-align:right;line-height:1.6}
.hinfo b{color:#f8fafc}
.main{max-width:1440px;margin:0 auto;padding:24px}

/* View Toggle */
.view-toggle{display:flex;background:#e2e8f0;padding:5px;border-radius:10px;margin-bottom:24px;width:fit-content;box-shadow:inset 0 2px 4px rgba(0,0,0,0.05);}
.vt-btn{padding:10px 24px;border-radius:8px;border:none;background:transparent;color:#64748b;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s;}
.vt-btn.active{background:#fff;color:#0f172a;box-shadow:0 2px 4px rgba(0,0,0,.05);}
.vt-btn svg{width:16px;height:16px;margin-right:6px;vertical-align:text-bottom;}

/* Info bar */
.info-bar{display:grid;grid-template-columns:1fr auto;gap:12px;margin-bottom:16px}
.info-pill-group{display:flex;gap:12px;flex-wrap:wrap}
.info-pill{background:var(--card);border-radius:12px;border:1px solid #e2e8f0;padding:12px 20px;display:flex;align-items:center;gap:12px;box-shadow:var(--shadow);overflow:hidden;flex:1}
.info-pill .ip-label{font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;flex-shrink:0}
.info-pill .ip-val{font-size:13px;font-family:ui-monospace,monospace;color:#334155;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.btn-group{display:flex;gap:10px;align-items:center}
.btn{padding:8px 16px;border-radius:8px;border:none;color:#fff;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;transition:background 0.2s;box-shadow:var(--shadow)}
.btn-primary{background:#6366f1}.btn-primary:hover{background:#4f46e5}
.btn-success{background:#10b981}.btn-success:hover{background:#059669}
.btn-dark{background:#1e293b}.btn-dark:hover{background:#0f172a}
.btn-outline{background:#fff;border:1px solid #cbd5e1;color:#334155;}.btn-outline:hover{background:#f1f5f9;}
.btn svg{transition:transform .5s}
.btn.spinning svg{animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Timeframe Bar */
.timeframe-bar{display:flex;justify-content:space-between;align-items:center;background:#fff;padding:12px 16px;border-radius:12px;border:1px solid #e2e8f0;box-shadow:var(--shadow);margin-bottom:24px;flex-wrap:wrap;gap:12px;}
.tf-presets{display:flex;gap:8px;flex-wrap:wrap;}
.tf-btn{padding:8px 14px;border-radius:6px;border:1px solid #e2e8f0;font-size:13px;font-weight:600;cursor:pointer;background:#f8fafc;color:#64748b;transition:all .15s;}
.tf-btn:hover{background:#e2e8f0;color:#334155;}
.tf-btn.active{background:#6366f1;color:#fff;border-color:#6366f1;}
.tf-custom{display:flex;align-items:center;gap:8px;background:#f8fafc;padding:4px 8px;border-radius:8px;border:1px solid #e2e8f0;}
.tf-custom span{font-size:13px;color:#64748b;font-weight:500;}
.tf-custom input{padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;outline:none;}
.tf-apply{padding:6px 14px;background:#334155;color:#fff;border:none;border-radius:6px;font-weight:600;font-size:13px;cursor:pointer;}

/* Summary cards */
.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:var(--card);border-radius:12px;border:1px solid #e2e8f0;padding:16px 20px;box-shadow:var(--shadow)}
.stat-card .lbl{font-size:11px;color:#64748b;font-weight:700;text-transform:uppercase;margin-bottom:8px}
.stat-card .val{font-size:32px;font-weight:700;color:var(--header);line-height:1}
.stat-card .sub{font-size:13px;color:#64748b;margin-top:6px}
.ok .val{color:#15803d}.warn .val{color:#b45309}.danger .val{color:#b91c1c}

/* Chart Container */
.chart-card{background:var(--card);border-radius:12px;border:1px solid #e2e8f0;padding:16px 20px;box-shadow:var(--shadow);margin-bottom:24px;}
.chart-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;}
.chart-header h3{font-size:15px;font-weight:600;color:#334155;}
.chart-wrap{height:220px;width:100%;}

/* Day tabs */
.day-tabs{display:flex;background:var(--card);border-radius:12px;border:1px solid #e2e8f0;margin-bottom:24px;box-shadow:var(--shadow);flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;scroll-behavior:smooth;}
.day-tabs::-webkit-scrollbar{height:8px;}
.day-tabs::-webkit-scrollbar-track{background:#f1f5f9;border-radius:0 0 12px 12px;}
.day-tabs::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:12px;}
.day-tab{flex:0 0 auto;min-width:115px;padding:12px 8px;text-align:center;cursor:pointer;border-right:1px solid #e2e8f0;border-bottom:3px solid transparent;font-size:13px;font-weight:500;color:#64748b;}
.day-tab:hover{background:#f8fafc}
.day-tab.active{background:#eef2ff;color:#4f46e5;border-bottom:3px solid #6366f1;}
.day-tab.has-missing{border-bottom-color:#fecaca;}
.day-tab.active.has-missing{border-bottom-color:#ef4444;}
.td{font-size:12px;font-weight:600;display:block;margin-bottom:4px}
.ts{font-size:11px;display:flex;justify-content:center;gap:8px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px;vertical-align:-1px}
.dg{background:#22c55e}.dr{background:#ef4444}

/* Day content */
.day-content{background:var(--card);border-radius:16px;border:1px solid #e2e8f0;padding:24px 32px;box-shadow:var(--shadow)}
.day-header{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:20px;flex-wrap:wrap;gap:12px}
.dh-left h3{font-size:20px;font-weight:700;color:var(--header);margin-bottom:4px}
.dmeta{font-size:14px;color:#64748b}

/* Progress bar */
.prog-wrap{margin-bottom:24px;background:#f8fafc;padding:16px;border-radius:12px;border:1px solid #f1f5f9}
.prog-row{display:flex;align-items:center;gap:12px}
.prog-bar-bg{flex:1;height:10px;background:#e2e8f0;border-radius:99px;overflow:hidden}
.prog-bar-fill{height:100%;border-radius:99px;transition:width .5s cubic-bezier(0.4, 0, 0.2, 1)}
.prog-pct{font-size:14px;font-weight:700;min-width:40px;text-align:right}

/* Filter bar & Multi-select */
.filter-bar{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;align-items:stretch;background:#f8fafc;padding:12px;border-radius:12px;border:1px solid #f1f5f9}
.filter-group{display:flex;gap:4px;background:#fff;padding:4px;border-radius:8px;border:1px solid #e2e8f0;align-items:center;}
.filter-bar input.main-search{flex:1;min-width:180px;padding:8px 16px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;background:#fff;}
.filter-bar input.main-search:focus{border-color:#6366f1;}

.ms-container{position:relative;min-width:220px;}
.ms-btn{width:100%;height:100%;text-align:left;padding:8px 14px;border:1px solid #e2e8f0;background:#fff;border-radius:8px;cursor:pointer;font-size:13px;display:flex;justify-content:space-between;align-items:center;color:#334155;font-weight:500;}
.ms-popover{position:absolute;top:100%;left:0;width:300px;background:#fff;border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 10px 25px -5px rgba(0,0,0,0.1);margin-top:6px;z-index:50;display:none;flex-direction:column;max-height:350px;}
.ms-popover.show{display:flex;}
.ms-search-box{padding:10px;border-bottom:1px solid #e2e8f0;}
.ms-search-box input{width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;outline:none;}
.ms-list{overflow-y:auto;flex:1;padding:6px;}
.ms-list label{display:flex;align-items:center;gap:10px;padding:8px 10px;font-size:13px;font-family:ui-monospace,monospace;cursor:pointer;border-radius:6px;}
.ms-list label:hover{background:#f1f5f9;}
.ms-footer{padding:10px;border-top:1px solid #e2e8f0;display:flex;gap:8px;}
.ms-footer button{flex:1;padding:6px;font-size:12px;font-weight:600;cursor:pointer;border-radius:6px;border:1px solid #e2e8f0;}

.type-btn, .status-btn{padding:6px 14px;border-radius:6px;border:none;font-size:13px;font-weight:600;cursor:pointer;background:transparent;color:#64748b;display:flex;align-items:center;gap:6px;}
.type-btn.active{background:#6366f1;color:#fff}
.status-btn.active{background:#e2e8f0;color:#0f172a}

.t-badge{font-size:10px;padding:2px 6px;border-radius:4px;font-weight:700;}
.tb-ok{background:#dcfce7;color:#166534;}
.tb-warn{background:#fef3c7;color:#b45309;}
.tb-bad{background:#fee2e2;color:#b91c1c;}
.type-btn.active .t-badge{background:#4f46e5;color:#fff;border:1px solid #818cf8;}

/* File chips */
.sh{display:flex;align-items:center;gap:10px;margin:24px 0 12px;padding-bottom:8px;border-bottom:1px solid #f1f5f9}
.sh h4{font-size:13px;font-weight:700;text-transform:uppercase;}
.badge{font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px}
.bg{background:var(--green-bg);color:var(--green);border:1px solid var(--green-border)}
.br{background:var(--red-bg);color:var(--red);border:1px solid var(--red-border)}
.files-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}
.file-chip{display:flex;align-items:flex-start;gap:10px;padding:12px 14px;border-radius:10px;font-size:13px;border:1px solid;background:#fff;}
.fc-ok{border-color:var(--green-border)}
.fc-miss{border-color:var(--red-border);background:var(--red-bg)}
.ci{width:18px;height:18px;flex-shrink:0;margin-top:2px}
.fc-details{display:flex;flex-direction:column;gap:5px;flex:1;overflow:hidden}
.fc-code{font-weight:600;color:#1e293b;display:flex;flex-wrap:wrap;gap:4px;align-items:baseline;}
.fname-bracket{font-weight:400;color:#64748b;font-size:11px;font-family:ui-monospace,monospace;word-break:break-all;}
.fc-meta{display:flex;align-items:center;gap:6px;font-size:11px;margin-top:2px;flex-wrap:wrap;}
.fc-time{color:#475569;display:flex;align-items:center;gap:4px;font-weight:500;background:#f1f5f9;padding:3px 8px;border-radius:6px;border:1px solid #e2e8f0;}
.fc-time svg{width:12px;height:12px;color:#6366f1;}
.cnp{font-size:11px;font-weight:600;background:var(--red);color:#fff;padding:3px 8px;border-radius:6px;}
.cnp-warn{background:#f59e0b;color:#fff;}
.cnt{font-size:11px;font-weight:700;background:var(--green);color:#fff;padding:2px 6px;border-radius:4px;}

/* REGISTRY VIEW STYLES */
.registry-wrap{background:var(--card);border-radius:16px;border:1px solid #e2e8f0;padding:32px;box-shadow:var(--shadow)}
.reg-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;border-bottom:1px solid #e2e8f0;padding-bottom:20px;}
.reg-search{padding:10px 16px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px;width:300px;outline:none;transition:border .2s;}
.reg-search:focus{border-color:#6366f1;}
.reg-table{width:100%;border-collapse:collapse;font-size:14px;text-align:left;}
.reg-table th{background:#f8fafc;padding:14px 16px;color:#475569;font-weight:700;text-transform:uppercase;border-bottom:2px solid #e2e8f0;letter-spacing:0.5px;}
.reg-table td{padding:14px 16px;border-bottom:1px solid #f1f5f9;color:#334155;}
.reg-table tr:hover td{background:#f8fafc;}
.rc-code{font-weight:600;font-family:ui-monospace,monospace;color:#0f172a;}
.rc-date{display:inline-flex;align-items:center;gap:6px;background:#f0fdf4;color:#15803d;padding:6px 12px;border-radius:20px;font-weight:600;font-size:12px;border:1px solid #bbf7d0;}
.rc-date svg{color:#16a34a;}

.emsg{text-align:center;padding:48px 24px;color:#64748b;font-size:15px;background:#f8fafc;border-radius:12px;border:2px dashed #e2e8f0;margin-top:12px}
.error-card{background:#fef2f2;border:1px solid #fca5a5;border-radius:12px;padding:20px 24px;color:#b91c1c;margin-bottom:24px}
.loading{text-align:center;padding:80px;color:#64748b;font-size:15px;font-weight:500}
.spinner{width:40px;height:40px;border:3px solid #e2e8f0;border-top-color:#6366f1;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px}
</style>
</head>
<body>
<header>
  <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="3"/><path d="M3 9h18M9 21V9"/></svg>
  <h1>Intelligent File Monitor</h1>
  <span class="hbadge" id="header-badge">Timeline Aware Tracking</span>
  <div class="hinfo" id="hinfo">Loading…</div>
</header>

<div class="main">

  <div class="view-toggle">
    <button class="vt-btn active" id="btn-view-monitor" onclick="switchView('monitor')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
      Live Monitoring Dashboard
    </button>
    <button class="vt-btn" id="btn-view-registry" onclick="switchView('registry')">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
      Code Tracking Registry
    </button>
  </div>

  <div class="info-bar">
    <div class="info-pill-group">
      <div class="info-pill"><span class="ip-label">Master List</span><span class="ip-val" id="master-path">—</span></div>
      <div class="info-pill"><span class="ip-label">Watch Dir</span><span class="ip-val" id="folder-path">—</span></div>
    </div>
    <div class="btn-group" id="monitor-btns">
      <button class="btn btn-success" onclick="downloadCSVReport()">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Export Monitor Data
      </button>
      <button class="btn btn-primary" id="refresh-btn" onclick="loadData()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        Refresh System
      </button>
    </div>
  </div>

  <div id="error-area"></div>
  <div id="loading" class="loading"><div class="spinner"></div>Loading Intelligent Tracking History…</div>
  
  <div id="view-monitor" style="display:none">
    <div class="timeframe-bar">
      <div class="tf-presets" id="tf-presets">
        <button class="tf-btn" data-preset="7d" onclick="setPresetRange('7d')">Last 7 Days</button>
        <button class="tf-btn" data-preset="month" onclick="setPresetRange('month')">This Month</button>
        <button class="tf-btn" data-preset="lastMonth" onclick="setPresetRange('lastMonth')">Last Month</button>
        <button class="tf-btn" data-preset="year" onclick="setPresetRange('year')">Yearwise (This Year)</button>
      </div>
      <div class="tf-custom">
        <span>From:</span><input type="date" id="tf-start">
        <span>To:</span><input type="date" id="tf-end">
        <button class="tf-apply" onclick="applyCustomDateRange()">Apply Dates</button>
      </div>
    </div>

    <div class="summary-grid" id="summary-grid"></div>
    
    <div class="chart-card">
      <div class="chart-header">
        <h3>File Coverage Timeline</h3>
        <button class="btn btn-outline" style="padding:4px 10px; font-size:11px;" onclick="downloadChartImage()">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Download Graph
        </button>
      </div>
      <div class="chart-wrap"><canvas id="trendChart"></canvas></div>
    </div>

    <div class="day-tabs" id="day-tabs"></div>
    <div class="day-content" id="day-content"></div>
  </div>

  <div id="view-registry" style="display:none" class="registry-wrap">
    <div class="reg-header">
      <div>
        <h3 style="font-size:22px;font-weight:700;color:var(--header);margin-bottom:6px;">Code Tracking Registry</h3>
        <p style="color:#64748b;font-size:14px;max-width:600px;">This directory shows the exact inception date for every master code extracted from your source files. The Monitor Dashboard uses this date to ensure codes are never flagged as "Missing" before they officially entered the system.</p>
      </div>
      <div style="display:flex;gap:12px;align-items:center;">
        <input type="text" class="reg-search" id="reg-search" placeholder="Search codes (e.g., UDRTA)..." oninput="renderRegistryTable()">
        <button class="btn btn-dark" onclick="downloadRegistryCSV()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          Export Registry
        </button>
      </div>
    </div>
    <div style="overflow-x:auto;">
      <table class="reg-table">
        <thead>
          <tr>
            <th>Master Code</th>
            <th>Entity</th>
            <th>Type</th>
            <th>Sub</th>
            <th>Tracking Start Date (Inception)</th>
          </tr>
        </thead>
        <tbody id="reg-tbody"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
let G = { 
  masterMap: {},     // Code -> Inception Date ("YYYYMMDD")
  masterCodes: [],   // Array of all keys
  byDate: {}, 
  days: [], 
  activeDay: null, 
  filterType: 'ALL', 
  filterStatus: 'ALL', 
  filterSearch: '', 
  selectedCodes: new Set(),
  chartInstance: null
};

/* --- Helpers --- */
function fmtDate(ds){
  const W=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'], M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const dt = new Date(+ds.slice(0,4), +ds.slice(4,6)-1, +ds.slice(6,8));
  return { 
    short: W[dt.getDay()]+' '+parseInt(ds.slice(6,8))+' '+M[+ds.slice(4,6)-1], 
    long: W[dt.getDay()]+', '+parseInt(ds.slice(6,8))+' '+M[+ds.slice(4,6)-1]+' '+ds.slice(0,4), 
    iso: ds.slice(0,4)+'-'+ds.slice(4,6)+'-'+ds.slice(6,8) 
  };
}

function getYYYYMMDD(dateObj) {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, '0');
  const d = String(dateObj.getDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

function toIsoDate(dateObj) {
  return getYYYYMMDD(dateObj).replace(/(\\d{4})(\\d{2})(\\d{2})/, '$1-$2-$3');
}

function formatDateTimeFull(unixSecs) {
  if(!unixSecs) return 'Time Unknown';
  const d = new Date(unixSecs * 1000);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${min}:${ss}`;
}

/* --- View Switching --- */
function switchView(viewName) {
  document.getElementById('view-monitor').style.display = viewName === 'monitor' ? 'block' : 'none';
  document.getElementById('view-registry').style.display = viewName === 'registry' ? 'block' : 'none';
  document.getElementById('monitor-btns').style.display = viewName === 'monitor' ? 'flex' : 'none';
  
  document.getElementById('btn-view-monitor').className = viewName === 'monitor' ? 'vt-btn active' : 'vt-btn';
  document.getElementById('btn-view-registry').className = viewName === 'registry' ? 'vt-btn active' : 'vt-btn';

  if(viewName === 'registry') renderRegistryTable();
}


/* --- Core Loading --- */
async function loadData(){
  document.getElementById('loading').style.display = 'block';
  document.getElementById('view-monitor').style.display = 'none';
  document.getElementById('view-registry').style.display = 'none';
  document.getElementById('error-area').innerHTML = '';
  document.getElementById('refresh-btn').classList.add('spinning');

  try{
    const res = await fetch('/api/files');
    const data = await res.json();
    document.getElementById('refresh-btn').classList.remove('spinning');
    document.getElementById('loading').style.display = 'none';

    if(data.error){
      document.getElementById('error-area').innerHTML = `<div class="error-card"><b>⚠ Error</b>${data.error}</div>`;
      return;
    }

    document.getElementById('master-path').textContent = data.master_txt;
    document.getElementById('folder-path').textContent = data.watch_folder;
    
    const now = new Date();
    document.getElementById('hinfo').innerHTML = `<b>${data.master_count}</b> Tracked Codes &nbsp;·&nbsp; <b>${data.total_scanned}</b> Total Files Found &nbsp;·&nbsp; System Refreshed ${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`;

    G.masterMap = data.master_codes_map;
    G.masterCodes = Object.keys(data.master_codes_map).sort();
    G.byDate = data.by_date;
    G.selectedCodes = new Set(G.masterCodes);
    
    // Switch to monitor and set default range
    switchView('monitor');
    setPresetRange('7d');
    
  } catch(e){
    document.getElementById('refresh-btn').classList.remove('spinning');
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error-area').innerHTML = `<div class="error-card"><b>Cannot Reach Server</b>Ensure server.py is running.</div>`;
  }
}

/* --- Date Range Filtering --- */
function setPresetRange(preset) {
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  const btn = document.querySelector(`.tf-btn[data-preset="${preset}"]`);
  if(btn) btn.classList.add('active');

  const today = new Date();
  const endDt = new Date(today);
  endDt.setDate(today.getDate() - 1); 
  let startDt = new Date(endDt);

  if (preset === '7d') {
    startDt.setDate(endDt.getDate() - 6);
  } else if (preset === 'month') {
    startDt = new Date(endDt.getFullYear(), endDt.getMonth(), 1);
  } else if (preset === 'lastMonth') {
    startDt = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    endDt.setTime(new Date(today.getFullYear(), today.getMonth(), 0).getTime());
  } else if (preset === 'year') {
    startDt = new Date(endDt.getFullYear(), 0, 1);
  }

  document.getElementById('tf-start').value = toIsoDate(startDt);
  document.getElementById('tf-end').value = toIsoDate(endDt);
  generateDaysArray(startDt, endDt);
}

function applyCustomDateRange() {
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  
  const startStr = document.getElementById('tf-start').value;
  const endStr = document.getElementById('tf-end').value;
  
  if(!startStr || !endStr) return;
  const startDt = new Date(startStr);
  const endDt = new Date(endStr);
  if (startDt > endDt) { alert("From date cannot be after To date."); return; }
  generateDaysArray(startDt, endDt);
}

function generateDaysArray(startDt, endDt) {
  G.days = [];
  let current = new Date(startDt);
  let safety = 0;
  while (current <= endDt && safety < 400) {
    G.days.push(getYYYYMMDD(current));
    current.setDate(current.getDate() + 1);
    safety++;
  }
  
  // Reverse days so newest is first in logic
  G.days.reverse(); 
  if(G.days.length > 0) G.activeDay = G.days[0];

  renderSummary();
  renderChart();
  renderTabs();
  renderDay();
}


/* ── Code Multi-Select Dropdown Logic ── */
function toggleMS() { document.getElementById('ms-pop').classList.toggle('show'); }
document.addEventListener('click', e => {
  if(!e.target.closest('.ms-container')) document.getElementById('ms-pop')?.classList.remove('show');
});

function renderCodeDropdown(){
  const list = document.getElementById('ms-list');
  list.innerHTML = G.masterCodes.map(c => `
    <label class="ms-lbl"><input type="checkbox" value="${c}" ${G.selectedCodes.has(c) ? 'checked' : ''} onchange="handleCodeCheck(this)">${c}</label>
  `).join('');
  updateMSBtnText();
}

function handleCodeCheck(cb){
  if(cb.checked) G.selectedCodes.add(cb.value); else G.selectedCodes.delete(cb.value);
  updateMSBtnText(); 
  renderSummary(); renderChart(); renderTabs(); renderDay();
}

function msSelectAll(){ G.masterCodes.forEach(c => G.selectedCodes.add(c)); renderCodeDropdown(); handleCodeCheck({checked:true}); }
function msClearAll(){ G.selectedCodes.clear(); renderCodeDropdown(); handleCodeCheck({checked:false}); }

function filterMSList(val){
  val = val.toLowerCase();
  document.querySelectorAll('#ms-list .ms-lbl').forEach(lbl => {
    lbl.style.display = lbl.textContent.toLowerCase().includes(val) ? 'flex' : 'none';
  });
}

function updateMSBtnText(){
  const btn = document.getElementById('ms-btn-text');
  if(G.selectedCodes.size === G.masterCodes.length) btn.textContent = 'All Codes Selected';
  else if(G.selectedCodes.size === 0) btn.textContent = '0 Selected (None)';
  else btn.textContent = `${G.selectedCodes.size} Selected`;
}

/* ── INTELLIGENT EXPECTED LOGIC ── */
// Returns True ONLY if the code is explicitly selected AND the target day is >= the code's inception date
function isCodeExpectedOnDay(code, dayStr) {
    if (!G.selectedCodes.has(code)) return false;
    const inception = G.masterMap[code];
    if (!inception) return false;
    return dayStr >= inception; 
}


/* ── Graphical Chart Logic ── */
function renderChart() {
  if (!window.Chart) return;
  const ctx = document.getElementById('trendChart');
  if (!ctx) return;

  const chronoDays = [...G.days].reverse();
  const labels = chronoDays.map(d => fmtDate(d).short);
  
  const dataPoints = chronoDays.map(d => {
    const dayMap = G.byDate[d] || {};
    let expectedCountForDay = 0;
    let presentCountForDay = 0;
    
    G.selectedCodes.forEach(c => {
      // Intelligent filter: only counts if the code was alive on this day
      if (isCodeExpectedOnDay(c, d)) {
          expectedCountForDay++;
          if (dayMap[c]) presentCountForDay++;
      }
    });
    
    return expectedCountForDay ? Math.round((presentCountForDay / expectedCountForDay) * 100) : 100; // If nothing expected, 100% covered.
  });

  if (G.chartInstance) G.chartInstance.destroy();

  G.chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Coverage (%)',
        data: dataPoints,
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99, 102, 241, 0.1)',
        borderWidth: 2,
        pointBackgroundColor: '#4f46e5',
        pointRadius: 3,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(ctx) { return ctx.raw + '% Covered'; } } } },
      scales: {
        y: { beginAtZero: true, max: 100, ticks: { callback: function(v){ return v+'%' } } },
        x: { grid: { display: false } }
      }
    }
  });
}

function downloadChartImage() {
  if(!G.chartInstance) return;
  const link = document.createElement('a');
  link.download = `Coverage_Trend_${fmtDate(G.days[G.days.length-1]).iso}.png`;
  const canvas = document.getElementById('trendChart');
  const context = canvas.getContext('2d');
  context.save();
  context.globalCompositeOperation = 'destination-over';
  context.fillStyle = 'white';
  context.fillRect(0, 0, canvas.width, canvas.height);
  link.href = canvas.toDataURL('image/png');
  context.restore();
  link.click();
}


/* ── UI Rendering ── */
function renderSummary(){
  const { byDate, days, activeDay } = G;
  if(!activeDay) return;
  const dayMap = byDate[activeDay] || {};
  
  let expDay = 0;
  let presDay = 0;
  G.selectedCodes.forEach(c => { 
      if(isCodeExpectedOnDay(c, activeDay)){
          expDay++;
          if(dayMap[c]) presDay++;
      }
  });
  
  const missDay = expDay - presDay;
  const pctDay = expDay ? Math.round((presDay/expDay)*100) : 100;

  document.getElementById('summary-grid').innerHTML = `
    <div class="stat-card ${missDay===0?'ok':missDay<5?'warn':'danger'}"><div class="lbl">Coverage (${fmtDate(activeDay).short})</div><div class="val">${expDay?pctDay:'N/A'}%</div><div class="sub">${presDay} of ${expDay} expected files</div></div>
    <div class="stat-card ${missDay===0?'ok':'danger'}"><div class="lbl">Missing (Active Tab)</div><div class="val">${missDay}</div><div class="sub">absent on selected date</div></div>
    <div class="stat-card"><div class="lbl">Timeline View</div><div class="val">${days.length}</div><div class="sub">days currently analyzed</div></div>
    <div class="stat-card"><div class="lbl">Active Tracking Limit</div><div class="val">${expDay}</div><div class="sub">codes registered by this date</div></div>
  `;
}

function renderTabs(){
  const { byDate, days, activeDay } = G;
  document.getElementById('day-tabs').innerHTML = days.map(d => {
    const dayMap = byDate[d] || {};
    let exp = 0;
    let p = 0;
    G.selectedCodes.forEach(c => { 
        if(isCodeExpectedOnDay(c, d)){
            exp++;
            if(dayMap[c]) p++;
        }
    });
    const m = exp - p;
    // Don't show missing state if nothing was expected anyway
    const noExp = exp === 0;
    return `<div class="day-tab${d===activeDay?' active':''}${m>0?' has-missing':''}" onclick="selectDay('${d}')">
      <span class="td">${fmtDate(d).short}</span><div class="ts"><span><span class="dot dg"></span>${p}</span><span><span class="dot ${m>0?'dr':'dgr'}"></span>${m}</span></div>
    </div>`;
  }).join('');
}

function selectDay(d){ G.activeDay=d; renderTabs(); renderDay(); renderSummary(); }
function setTypeFilter(t){ G.filterType=t; document.querySelectorAll('.type-btn').forEach(b=>b.classList.toggle('active',b.dataset.type===t)); renderFilesList(); }
function setStatusFilter(s){ G.filterStatus=s; document.querySelectorAll('.status-btn').forEach(b=>b.classList.toggle('active',b.dataset.status===s)); renderFilesList(); }
function setSearch(v){ G.filterSearch=v.toLowerCase(); renderFilesList(); }

function renderDay(){
  const { byDate, activeDay, selectedCodes } = G;
  if(!activeDay) {
      document.getElementById('day-content').innerHTML = `<div class="emsg">No date range selected.</div>`;
      return;
  }

  const dayMap = byDate[activeDay] || {};
  let expTotal = 0;
  let pTotal = 0;
  
  // Calculate Type Statistics intelligently based on inception dates
  const types = [...new Set(Array.from(selectedCodes).map(c=>c.split('_')[1]))].sort();
  const typeStats = {};
  types.forEach(t => typeStats[t] = { expected: 0, present: 0 });
  
  selectedCodes.forEach(c => { 
      if (isCodeExpectedOnDay(c, activeDay)) {
          expTotal++;
          const t = c.split('_')[1];
          if(typeStats[t] !== undefined) {
              typeStats[t].expected++;
              if(dayMap[c]) {
                  typeStats[t].present++;
                  pTotal++;
              }
          }
      }
  });

  const mTotal = expTotal - pTotal;
  const pct = expTotal ? Math.round((pTotal/expTotal)*100) : 100;
  const barColor = pct >= 95 ? '#16a34a' : pct >= 75 ? '#d97706' : '#dc2626';

  document.getElementById('day-content').innerHTML = `
    <div class="day-header">
      <div class="dh-left"><h3>File Details for ${fmtDate(activeDay).long}</h3>
      <div class="dmeta">${pTotal} Found &nbsp;·&nbsp; ${mTotal} Missing &nbsp;·&nbsp; ${expTotal} Expected (Tracking Aware)</div></div>
    </div>
    
    ${expTotal > 0 ? `<div class="prog-wrap"><div class="prog-row"><div class="prog-bar-bg"><div class="prog-bar-fill" style="width:${pct}%;background:${barColor}"></div></div><span class="prog-pct" style="color:${barColor}">${pct}%</span></div></div>` : `<div class="emsg" style="margin-bottom:20px;padding:20px;">No codes were registered for tracking on this date yet.</div>`}
    
    <div class="filter-bar">
      <div class="ms-container" id="ms-container">
        <button class="ms-btn" onclick="toggleMS()">
          <span id="ms-btn-text">All Codes Selected</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
        </button>
        <div class="ms-popover" id="ms-pop">
          <div class="ms-search-box"><input type="text" placeholder="Search codes in list..." oninput="filterMSList(this.value)"></div>
          <div class="ms-list" id="ms-list"></div>
          <div class="ms-footer"><button onclick="msSelectAll()">Select All</button><button onclick="msClearAll()">Clear All</button></div>
        </div>
      </div>
      
      <input type="text" class="main-search" placeholder="Text search (e.g. DEL)..." oninput="setSearch(this.value)" value="${G.filterSearch}">
      
      <div class="filter-group">
        <button class="status-btn ${G.filterStatus==='ALL'?'active':''}" data-status="ALL" onclick="setStatusFilter('ALL')">All</button>
        <button class="status-btn ${G.filterStatus==='PRESENT'?'active':''}" data-status="PRESENT" onclick="setStatusFilter('PRESENT')">Present</button>
        <button class="status-btn ${G.filterStatus==='MISSING'?'active':''}" data-status="MISSING" onclick="setStatusFilter('MISSING')">Missing</button>
      </div>
      
      <div class="filter-group" id="type-filters" style="flex-wrap:wrap">
        <button class="type-btn ${G.filterType==='ALL'?'active':''}" data-type="ALL" onclick="setTypeFilter('ALL')">All Types</button>
        ${types.map(t => {
            const stats = typeStats[t];
            if (stats.expected === 0) return ''; // Hide types that didn't exist yet
            const p = Math.round((stats.present / stats.expected) * 100);
            const badgeClass = p >= 95 ? 'tb-ok' : p >= 50 ? 'tb-warn' : 'tb-bad';
            return `<button class="type-btn ${G.filterType===t?'active':''}" data-type="${t}" onclick="setTypeFilter('${t}')">
                ${t} <span class="t-badge ${badgeClass}">${p}%</span>
            </button>`;
        }).join('')}
      </div>
    </div>
    <div id="files-list"></div>`;
    
  renderCodeDropdown(); 
  renderFilesList();
}

function renderFilesList(){
  const { byDate, activeDay, filterType, filterStatus, filterSearch } = G;
  const dayMap = byDate[activeDay] || {};

  const matchesFilter = c =>
    (filterType === 'ALL' || c.split('_')[1] === filterType) &&
    (!filterSearch || c.toLowerCase().includes(filterSearch));

  let fp = [];
  let fm = [];
  let futureCodes = 0; // Codes ignored because their inception date is in the future

  G.masterCodes.forEach(c => {
      if (!G.selectedCodes.has(c)) return;
      if (!matchesFilter(c)) return;
      
      if (!isCodeExpectedOnDay(c, activeDay)) {
          // It's not expected yet. If it's somehow found early, we can still list it as present.
          if(dayMap[c]) fp.push(c);
          else futureCodes++;
          return;
      }
      
      if (dayMap[c]) fp.push(c);
      else fm.push(c);
  });

  if (filterStatus === 'PRESENT') fm = [];
  if (filterStatus === 'MISSING') fp = [];

  const iconOk   = `<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
  const iconMiss = `<svg class="ci" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
  const iconTime = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;

  let html = '';

  if(fp.length){
    html += `<div class="sh"><h4 style="color:var(--green)">Present Files</h4><span class="badge bg">${fp.length}</span></div><div class="files-grid">`;
    fp.forEach(c => {
      const files = (dayMap[c] || []).sort((a,b)=> b.mtime - a.mtime);
      const latest = files[0];
      const p = c.split('_');
      html += `<div class="file-chip fc-ok">
        ${iconOk}
        <div class="fc-details">
          <span class="fc-code"><b>${p[0]}</b>_${p[1]}_${p[2]} <span class="fname-bracket">(${latest.name})</span></span>
          <div class="fc-meta">
            <span class="fc-time" title="Exact Receive Date/Time">${iconTime} ${formatDateTimeFull(latest.mtime)}</span>
            ${!isCodeExpectedOnDay(c, activeDay) ? '<span class="cnp cnp-warn">Early File</span>' : ''}
          </div>
        </div>
      </div>`;
    });
    html += '</div>';
  }

  if(fm.length){
    html += `<div class="sh" style="margin-top:${fp.length?'24px':'0'}"><h4 style="color:var(--red)">Missing Files</h4><span class="badge br">${fm.length}</span></div><div class="files-grid">`;
    fm.forEach(c => {
      const p = c.split('_');
      const expectedFname = `${c}_${activeDay}.csv`.toLowerCase(); 
      html += `<div class="file-chip fc-miss">
        ${iconMiss}
        <div class="fc-details">
          <span class="fc-code"><b>${p[0]}</b>_${p[1]}_${p[2]} <span class="fname-bracket">(Expected: ${expectedFname})</span></span>
          <div class="fc-meta"><span class="cnp">Awaiting File Ingestion</span></div>
        </div>
      </div>`;
    });
    html += '</div>';
  }

  if(!fp.length && !fm.length) {
      if(futureCodes > 0 && filterStatus !== 'PRESENT') {
          html = `<div class="emsg"><div style="font-size:24px;margin-bottom:8px">⏳</div><b>Codes are not active yet.</b><br>${futureCodes} selected codes match your filter, but their tracking start date is after ${fmtDate(activeDay).short}.</div>`;
      } else {
          html = `<div class="emsg"><div style="font-size:24px;margin-bottom:8px">🔍</div><b>No codes found.</b><br>Check your selections or text filter.</div>`;
      }
  }
  
  document.getElementById('files-list').innerHTML = html;
}

/* ── Code Registry View ── */
function renderRegistryTable() {
    const search = document.getElementById('reg-search').value.toLowerCase();
    let html = '';
    
    // Sort codes alphabetically
    const codes = [...G.masterCodes].sort();
    
    codes.forEach(c => {
        if (search && !c.toLowerCase().includes(search)) return;
        
        const parts = c.split('_');
        const dStr = G.masterMap[c];
        const dateFmt = fmtDate(dStr).long;
        
        html += `<tr>
            <td class="rc-code">${c}</td>
            <td>${parts[0]}</td>
            <td>${parts[1]}</td>
            <td>${parts[2]}</td>
            <td><span class="rc-date"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg> ${dateFmt}</span></td>
        </tr>`;
    });
    
    if(!html) html = `<tr><td colspan="5" style="text-align:center;padding:30px;color:#64748b;">No codes match your search.</td></tr>`;
    
    document.getElementById('reg-tbody').innerHTML = html;
}

function downloadRegistryCSV() {
    let csv = "Master_Code,Entity,Type,Subcode,Tracking_Start_Date_YYYYMMDD,Tracking_Start_Date_Formatted\\n";
    G.masterCodes.forEach(c => {
        const p = c.split('_');
        const ds = G.masterMap[c];
        const iso = fmtDate(ds).iso;
        csv += `${c},${p[0]},${p[1]},${p[2]},${ds},${iso}\\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', '');
    a.setAttribute('href', url);
    a.setAttribute('download', `Code_Tracking_Registry.csv`);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}


/* ── Dynamic CSV Report Generation ── */
function downloadCSVReport() {
  if (G.selectedCodes.size === 0) { alert("Please select at least one code to export."); return; }
  if (G.days.length === 0) { alert("No valid dates selected in the timeframe."); return; }
  
  let csv = "Expected_Date,Master_Code,Entity,Type,Subcode,Status,Actual_Filename,Received_Date_Time\\n";
  const reportDays = [...G.days].reverse();

  reportDays.forEach(day => {
    const dayMap = G.byDate[day] || {};
    const isoD = fmtDate(day).iso;
    
    G.masterCodes.forEach(code => {
      if (!G.selectedCodes.has(code)) return;
      
      // Intelligent filter: Don't export as MISSING if the code didn't exist yet
      if (!isCodeExpectedOnDay(code, day)) {
          // If it was somehow found early, we still export it
          if(dayMap[code]) {
              const parts = code.split('_');
              dayMap[code].forEach(f => {
                  csv += `${isoD},${code},${parts[0]},${parts[1]},${parts[2]},PRESENT_EARLY,${f.name},${formatDateTimeFull(f.mtime)}\\n`;
              });
          }
          return; 
      }
      
      const parts = code.split('_');
      const files = dayMap[code] || [];
      
      if (files.length > 0) {
        files.forEach(f => {
          csv += `${isoD},${code},${parts[0]},${parts[1]},${parts[2]},PRESENT,${f.name},${formatDateTimeFull(f.mtime)}\\n`;
        });
      } else {
        csv += `${isoD},${code},${parts[0]},${parts[1]},${parts[2]},MISSING,N/A,N/A\\n`;
      }
    });
  });

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.setAttribute('hidden', '');
  a.setAttribute('href', url);
  a.setAttribute('download', `Timeline_Coverage_Report_${fmtDate(reportDays[0]).iso}_to_${fmtDate(reportDays[reportDays.length-1]).iso}.csv`);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

window.addEventListener('load', loadData);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────
#  HTTP Server
# ─────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass   # suppress per-request noise; keep console clean

    def do_GET(self):
        if self.path == "/api/files":
            body = json.dumps(build_api_response()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        elif self.path in ("/", "/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()


# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    setup_ok = True

    if MASTER_TXT == r"C:\your\path\to\filenames.txt":
        print("  ✗  MASTER_TXT not set — open server.py and set MASTER_TXT")
        setup_ok = False

    if WATCH_FOLDER == r"C:\your\folder\path\here":
        print("  ✗  WATCH_FOLDER not set — open server.py and set WATCH_FOLDER")
        setup_ok = False

    if not setup_ok:
        print("\n  Edit the two paths at the top of server.py, then run again.")
    else:
        print("=" * 62)
        print("  Intelligent File Monitor (V8 - Backslash Safe Edition)")
        print(f"  Master TXT   : {MASTER_TXT}")
        print(f"  Watch Folder : {WATCH_FOLDER}")
        print(f"  Server       : http://localhost:{PORT}")
        print("  Open the URL above in your browser.")
        print("  Press Ctrl+C to stop.")
        print("=" * 62)
        server = HTTPServer(("localhost", PORT), Handler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n  Server stopped.")