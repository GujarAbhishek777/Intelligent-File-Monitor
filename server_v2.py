"""
File Monitor Dashboard V2.1 — 5-Sheet Comparison Edition
=======================================================
HOW IT WORKS:
  1. Configure 5 MASTER_TXT paths below (one per sheet type)
  2. WATCH_FILE → A text file containing the list of received .TXT filenames
  3. Run:  python server_v2.py
  4. Open: http://localhost:8785
"""

import os
import json
from datetime import datetime, timedelta, date
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─────────────────────────────────────────────────────────────────
#  CONFIGURE: 5 MASTER TXT PATHS + WATCH FILE
# ─────────────────────────────────────────────────────────────────

SHEETS = {
    "International": r"C:\Users\fgp.pgp\Desktop\TIC_Aniket\Aniket\International.txt",
    "OCI":           r"C:\Users\fgp.pgp\Desktop\TIC_Aniket\Aniket\OCI.txt",
    "Amma":          r"C:\Users\fgp.pgp\Desktop\TIC_Aniket\Aniket\Amma.txt",
    "Opera Cloud":   r"C:\Users\fgp.pgp\Desktop\TIC_Aniket\Aniket\Opera Cloud.txt",
    "Standalone":    r"C:\Users\fgp.pgp\Desktop\TIC_Aniket\Aniket\Standalone.txt",
}

# Now pointing to a text file containing the filenames
WATCH_FILE = r"C:\Users\fgp.pgp\Desktop\Aniket\filenames.txt"

# ─────────────────────────────────────────────────────────────────
PORT = 8785
# ─────────────────────────────────────────────────────────────────

MONTH_LETTERS = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6,
    'G': 7, 'H': 8, 'I': 9, 'J': 10, 'K': 11, 'L': 12
}


def parse_filename(fname):
    """
    Parse a filename like 4J914E26.TXT
    Returns dict with extracted details or None if invalid.
    """
    name = fname.strip()
    if "]" in name:
        name = name.split("]")[-1].strip()

    if '.' in name:
        name = name.rsplit('.', 1)[0]

    if len(name) < 7:
        return None

    file_type = name[0]
    if file_type not in ('4', '5', '6'):
        return None

    hotel_code = name[1:3]
    date_part = name[3:]

    if len(date_part) < 4:
        return None

    day_str = date_part[:2]
    month_letter = date_part[2].upper()
    year_str = date_part[3:5]

    if not day_str.isdigit() or not year_str.isdigit():
        return None

    if month_letter not in MONTH_LETTERS:
        return None

    day = int(day_str)
    month = MONTH_LETTERS[month_letter]
    year = 2000 + int(year_str)

    try:
        dt = date(year, month, day)
    except ValueError:
        return None

    # SHIFT BY +1 DAY:
    # A file with '16' in the name belongs to the physical reporting day of the '17th'.
    # This automatically maps business date files to the next morning's viewing date.
    display_dt = dt + timedelta(days=1)
    date_str = display_dt.strftime("%Y%m%d")

    return {
        "file_type": file_type,
        "hotel_code": hotel_code,
        "code": f"{file_type}{hotel_code}",
        "date_str": date_str,
    }


def load_master_codes(txt_path):
    """
    Load all valid codes from a master .txt file. 
    Returns a dict: { code -> start_date_str }
    This ensures tracking only begins ON OR AFTER the date listed in the master file.
    """
    if not os.path.isfile(txt_path):
        return None, f"Master file not found: {txt_path}"

    codes = {}
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parsed = parse_filename(line)
            if parsed:
                code = parsed["code"]
                date_str = parsed["date_str"]
                
                # If a code appears multiple times, track it starting from the earliest occurrence
                if code not in codes or date_str < codes[code]:
                    codes[code] = date_str

    if not codes:
        return None, "No valid codes found in master txt."

    return codes, None


def scan_watch_file():
    """
    Scan WATCH_FILE (a text file) for all valid .TXT filenames.
    Returns dict: { date_str (YYYYMMDD) -> { code -> [{ name, file_type, hotel_code, mtime }] } }
    """
    if not os.path.isfile(WATCH_FILE):
        return None, f"Watch file not found: {WATCH_FILE}"

    try:
        with open(WATCH_FILE, "r", encoding="utf-8") as f:
            # Read all lines and filter for strings ending in .TXT
            all_files = [line.strip() for line in f if line.strip().upper().endswith(".TXT")]
    except PermissionError as e:
        return None, str(e)

    by_date = {}
    for fname in all_files:
        parsed = parse_filename(fname)
        if not parsed:
            continue
            
        ds = parsed["date_str"]
        code = parsed["code"]
        
        # We don't have physical files, so modification time is 0 (frontend will show as '—')
        mtime = 0

        by_date.setdefault(ds, {}).setdefault(code, []).append({
            "name": fname,
            "file_type": parsed["file_type"],
            "hotel_code": parsed["hotel_code"],
            "mtime": mtime,
        })

    return by_date, None


def build_api_response():
    # Load all 5 master sheets
    sheets_data = {}
    for sheet_name, txt_path in SHEETS.items():
        codes_dict, err = load_master_codes(txt_path)
        if err:
            sheets_data[sheet_name] = {"error": err, "codes": {}}
        else:
            sheets_data[sheet_name] = {"codes": codes_dict}

    # Scan watch file instead of folder
    by_date, err = scan_watch_file()
    if err:
        return {"error": err, "error_source": "watch_file"}

    # Collect all unique file types across all sheets
    all_file_types = set()
    for sd in sheets_data.values():
        for code in sd.get("codes", {}).keys():
            all_file_types.add(code[0])

    # Ensure the literal current day is passed to the UI
    today = date.today()
    today_str = today.strftime("%Y%m%d")

    return {
        "sheets": sheets_data,
        "by_date": by_date,
        "watch_folder": WATCH_FILE,
        "today_str": today_str,
        "all_file_types": sorted(all_file_types),
    }


# ─────────────────────────────────────────────────────────────────
#  HTML DASHBOARD
# ─────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>File Monitor — 5 Sheet Comparison</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b22;--surface2:#21262d;--surface3:#30363d;
  --border:#30363d;--border2:#444c56;
  --text:#e6edf3;--text2:#8b949e;--text3:#6e7681;
  --green:#3fb950;--green-bg:rgba(63,185,80,.1);--green-border:rgba(63,185,80,.3);
  --red:#f85149;--red-bg:rgba(248,81,73,.1);--red-border:rgba(248,81,73,.3);
  --yellow:#d29922;--yellow-bg:rgba(210,153,34,.1);
  --blue:#58a6ff;--blue-bg:rgba(88,166,255,.1);
  --purple:#bc8cff;--purple-bg:rgba(188,140,255,.1);
  --orange:#ffa657;--orange-bg:rgba(255,166,87,.1);
  --teal:#39d353;
  --radius:10px;--radius-lg:14px;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* Header */
header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 28px;display:flex;align-items:center;gap:16px;flex-wrap:wrap;position:sticky;top:0;z-index:100}
.logo{display:flex;align-items:center;gap:10px}
.logo svg{color:var(--blue)}
.logo h1{font-size:17px;font-weight:700;letter-spacing:-0.4px;color:var(--text)}
.hbadge{font-size:11px;background:var(--blue-bg);color:var(--blue);padding:3px 10px;border-radius:20px;font-weight:600;border:1px solid rgba(88,166,255,.25)}
.hstats{margin-left:auto;display:flex;gap:20px;align-items:center}
.hstat{font-size:13px;color:var(--text2)}
.hstat b{color:var(--text);font-weight:600}
.btn-refresh{display:flex;align-items:center;gap:6px;padding:8px 14px;background:var(--surface2);border:1px solid var(--border2);color:var(--text);border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.btn-refresh:hover{background:var(--surface3);border-color:var(--blue)}
.btn-refresh svg{transition:transform .5s}
.btn-refresh.spin svg{animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Layout */
.main{max-width:1600px;margin:0 auto;padding:24px 28px}

/* View Toggle */
.view-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;gap:16px;flex-wrap:wrap}
.view-toggle{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:4px;gap:2px}
.vt{padding:8px 18px;border-radius:7px;border:none;background:transparent;color:var(--text2);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s;display:flex;align-items:center;gap:7px}
.vt.active{background:var(--surface3);color:var(--text);box-shadow:0 1px 3px rgba(0,0,0,.3)}
.vt svg{width:14px;height:14px}

/* Date toggle */
.date-toggle{display:flex;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:4px;gap:2px}
.dt-btn{padding:8px 20px;border-radius:7px;border:none;background:transparent;color:var(--text2);font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.dt-btn.active{background:var(--blue);color:#fff;box-shadow:0 2px 8px rgba(88,166,255,.3)}

/* Filters */
.filter-row{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center;background:var(--surface);padding:12px 16px;border-radius:var(--radius);border:1px solid var(--border)}
.filter-label{font-size:12px;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.chip-group{display:flex;gap:6px;flex-wrap:wrap}
.chip{padding:5px 13px;border-radius:20px;border:1px solid var(--border2);background:transparent;color:var(--text2);font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.chip:hover{border-color:var(--blue);color:var(--blue)}
.chip.active{background:var(--blue);color:#fff;border-color:var(--blue);box-shadow:0 2px 8px rgba(88,166,255,.25)}
.chip.sheet-International.active{background:#3fb950;border-color:#3fb950;box-shadow:0 2px 8px rgba(63,185,80,.25)}
.chip.sheet-OCI.active{background:#58a6ff;border-color:#58a6ff;box-shadow:0 2px 8px rgba(88,166,255,.25)}
.chip.sheet-Amma.active{background:#bc8cff;border-color:#bc8cff;box-shadow:0 2px 8px rgba(188,140,255,.25)}
.chip.sheet-OpCloud.active{background:#ffa657;border-color:#ffa657;box-shadow:0 2px 8px rgba(255,166,87,.25)}
.chip.sheet-Standalone.active{background:#f85149;border-color:#f85149;box-shadow:0 2px 8px rgba(248,81,73,.25)}
.sep{width:1px;height:20px;background:var(--border);margin:0 4px}
.search-input{padding:6px 12px;background:var(--surface2);border:1px solid var(--border2);border-radius:7px;color:var(--text);font-size:13px;font-family:inherit;outline:none;min-width:180px}
.search-input:focus{border-color:var(--blue)}

/* Overview Grid */
.ov-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:28px}
.ov-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:20px 22px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.ov-card:hover{border-color:var(--border2);transform:translateY(-1px);box-shadow:0 8px 24px rgba(0,0,0,.2)}
.ov-card.selected{border-color:var(--blue);box-shadow:0 0 0 1px var(--blue)}
.ov-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.ov-card.International::before{background:#3fb950}
.ov-card.OCI::before{background:#58a6ff}
.ov-card.Amma::before{background:#bc8cff}
.ov-card.Opera_Cloud::before{background:#ffa657}
.ov-card.Standalone::before{background:#f85149}
.ov-card .ov-name{font-size:13px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:12px}
.ov-card .ov-pct{font-size:48px;font-weight:700;line-height:1;margin-bottom:6px;font-family:'DM Mono',monospace}
.pct-green{color:var(--green)}
.pct-yellow{color:var(--yellow)}
.pct-red{color:var(--red)}
.ov-card .ov-sub{font-size:13px;color:var(--text2);margin-bottom:14px}
.ov-pbar{height:5px;background:var(--surface3);border-radius:99px;overflow:hidden;margin-bottom:10px}
.ov-pbar-fill{height:100%;border-radius:99px;transition:width .6s cubic-bezier(.4,0,.2,1)}
.ov-counts{display:flex;gap:14px}
.ov-count{font-size:12px;display:flex;align-items:center;gap:5px}
.ov-count .dot{width:7px;height:7px;border-radius:50%;display:inline-block}

/* Detail Table */
.detail-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;margin-bottom:20px}
.detail-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.detail-header h3{font-size:15px;font-weight:700;color:var(--text)}
.detail-header .dh-meta{font-size:13px;color:var(--text2)}
.export-btn{display:flex;align-items:center;gap:6px;padding:6px 14px;background:var(--surface2);border:1px solid var(--border2);color:var(--text);border-radius:7px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:all .15s}
.export-btn:hover{border-color:var(--green);color:var(--green)}

/* Day rows */
.day-section{border-bottom:1px solid var(--border)}
.day-section:last-child{border-bottom:none}
.day-row{display:flex;align-items:center;padding:12px 20px;cursor:pointer;transition:background .1s;gap:12px}
.day-row:hover{background:var(--surface2)}
.day-row.expanded{background:var(--surface2)}
.dr-date{font-size:13px;font-weight:600;color:var(--text);width:120px;flex-shrink:0;font-family:'DM Mono',monospace}
.dr-day{font-size:11px;color:var(--text3);width:40px;flex-shrink:0}
.dr-bar{flex:1;height:8px;background:var(--surface3);border-radius:99px;overflow:hidden;max-width:300px}
.dr-bar-fill{height:100%;border-radius:99px}
.dr-pct{font-size:13px;font-weight:700;width:42px;text-align:right;font-family:'DM Mono',monospace}
.dr-counts{display:flex;gap:14px;margin-left:auto}
.dr-count{font-size:12px;color:var(--text2);display:flex;align-items:center;gap:5px;white-space:nowrap}
.dr-chev{color:var(--text3);transition:transform .2s;margin-left:6px}
.day-row.expanded .dr-chev{transform:rotate(90deg)}

/* Expanded files */
.day-files{display:none;padding:6px 20px 16px 140px;background:var(--surface2)}
.day-files.open{display:block}
.files-grid-inner{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}
.fchip{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border-radius:8px;border:1px solid;font-size:12px}
.fchip-ok{border-color:var(--green-border);background:var(--green-bg)}
.fchip-miss{border-color:var(--red-border);background:var(--red-bg)}
.fchip-icon{flex-shrink:0;margin-top:1px}
.fchip-name{font-family:'DM Mono',monospace;font-weight:500;color:var(--text);word-break:break-all}
.fchip-meta{color:var(--text2);margin-top:3px;font-size:11px}
.fchip-miss .fchip-name{color:var(--red);opacity:.8}
.fchip-miss .fchip-meta{color:var(--text3)}

/* Section separators */
.sec-head{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text3);letter-spacing:.6px;padding:10px 0 6px;display:flex;align-items:center;gap:8px;margin-top:4px}
.sec-head::after{content:'';flex:1;height:1px;background:var(--border)}
.sec-count{background:var(--surface3);color:var(--text2);padding:2px 8px;border-radius:10px;font-size:11px}

/* Sheet pills */
.sheet-pill{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;margin-left:4px;vertical-align:middle}
.sp-International{background:rgba(63,185,80,.15);color:#3fb950}
.sp-OCI{background:rgba(88,166,255,.15);color:#58a6ff}
.sp-Amma{background:rgba(188,140,255,.15);color:#bc8cff}
.sp-Opera_Cloud{background:rgba(255,166,87,.15);color:#ffa657}
.sp-Standalone{background:rgba(248,81,73,.15);color:#f85149}

/* Empty/loading */
.empty{text-align:center;padding:60px;color:var(--text3);font-size:14px}
.spinner{width:36px;height:36px;border:3px solid var(--surface3);border-top-color:var(--blue);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px}
.loading{text-align:center;padding:80px;color:var(--text2)}
.err-card{background:rgba(248,81,73,.08);border:1px solid var(--red-border);border-radius:var(--radius);padding:16px 20px;color:var(--red);margin-bottom:20px;font-size:14px}

/* Summary pill row */
.sum-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.sum-pill{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px}
.sum-pill .sp-lbl{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text3);letter-spacing:.5px;margin-bottom:6px}
.sum-pill .sp-val{font-size:26px;font-weight:700;font-family:'DM Mono',monospace;line-height:1}
.sum-pill .sp-sub{font-size:12px;color:var(--text2);margin-top:4px}
</style>
</head>
<body>
<header>
  <div class="logo">
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
    <h1>File Monitor — 5-Sheet Comparison</h1>
  </div>
  <span class="hbadge">Multi-Sheet Tracking</span>
  <div class="hstats">
    <span class="hstat" id="h-codes">—</span>
    <span class="hstat" id="h-files">—</span>
    <span class="hstat" id="h-refresh">—</span>
  </div>
  <button class="btn-refresh" id="refresh-btn" onclick="loadData()">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
    Refresh
  </button>
</header>

<div class="main">
  <div id="error-area"></div>
  <div id="loading" class="loading"><div class="spinner"></div>Loading dashboard…</div>
  <div id="app" style="display:none">

    <div class="view-bar">
      <div class="view-toggle">
        <button class="vt active" id="vt-overview" onclick="setView('overview')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          Overview
        </button>
        <button class="vt" id="vt-detail" onclick="setView('detail')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
          Daily Detail
        </button>
      </div>
      <div class="date-toggle">
        <button class="dt-btn active" id="dt-today" onclick="setDateView('today')">Today</button>
        <button class="dt-btn" id="dt-week" onclick="setDateView('week')">Last 7 Days</button>
        <button class="dt-btn" id="dt-month" onclick="setDateView('month')">This Month</button>
      </div>
    </div>

    <div class="filter-row">
      <span class="filter-label">Sheet</span>
      <div class="chip-group" id="sheet-filter"></div>
      <div class="sep"></div>
      <span class="filter-label">Type</span>
      <div class="chip-group" id="type-filter"></div>
      <div class="sep"></div>
      <input class="search-input" type="text" placeholder="Search code…" id="search-input" oninput="applyFilters()">
      <button class="export-btn" onclick="downloadCSV()" style="margin-left:auto">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Export CSV
      </button>
    </div>

    <div id="view-overview"></div>
    <div id="view-detail" style="display:none"></div>
  </div>
</div>

<script>
const SHEET_COLORS = {
  'International': '#3fb950',
  'OCI':           '#58a6ff',
  'Amma':          '#bc8cff',
  'Opera Cloud':   '#ffa657',
  'Standalone':    '#f85149',
};
const SHEET_NAMES = ['International','OCI','Amma','Opera Cloud','Standalone'];

const G = {
  sheets: {},         // { sheetName: { codes: {code: startDate}, error? } }
  byDate: {},         // { YYYYMMDD: { code: [files] } }
  todayStr: '',       // Sent exactly as server's true current day
  allFileTypes: [],
  // Filter state
  activeSheets: new Set(SHEET_NAMES),
  activeTypes: new Set(),
  searchText: '',
  // View state
  view: 'overview',
  dateView: 'today',
  expandedDays: new Set(),
};

/* ── helpers ── */
function yyyymmdd(d){ return d.toISOString().slice(0,10).replace(/-/g,''); }
function fmtDate(ds){
  const dt = new Date(+ds.slice(0,4), +ds.slice(4,6)-1, +ds.slice(6,8));
  const days=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return {
    short: days[dt.getDay()]+' '+parseInt(ds.slice(6,8))+' '+months[+ds.slice(4,6)-1],
    day: days[dt.getDay()],
    iso: ds.slice(0,4)+'-'+ds.slice(4,6)+'-'+ds.slice(6,8),
    monthYear: months[+ds.slice(4,6)-1]+' '+ds.slice(0,4)
  };
}
function fmtTime(unix){ if(!unix) return '—'; const d=new Date(unix*1000); return d.toLocaleString(); }

// Helper to determine what filename to expect for a given reporting display date
function getExpectedFileName(code, displayDs) {
  const targetY = parseInt(displayDs.slice(0,4), 10);
  const targetM = parseInt(displayDs.slice(4,6), 10) - 1;
  const targetD = parseInt(displayDs.slice(6,8), 10);
  const d = new Date(targetY, targetM, targetD);
  
  // Subtract 1 day to get the actual business date 
  d.setDate(d.getDate() - 1);
  
  const dayStr = String(d.getDate()).padStart(2, '0');
  const monthLetters = ['A','B','C','D','E','F','G','H','I','J','K','L'];
  const monthL = monthLetters[d.getMonth()];
  const yearStr = String(d.getFullYear()).slice(-2);
  
  return `${code}${dayStr}${monthL}${yearStr}.TXT`;
}

function getActiveDays(){
  const targetY = parseInt(G.todayStr.slice(0,4), 10);
  const targetM = parseInt(G.todayStr.slice(4,6), 10) - 1;
  const targetD = parseInt(G.todayStr.slice(6,8), 10);
  const actualToday = new Date(targetY, targetM, targetD);

  if(G.dateView === 'today') return [G.todayStr];
  
  const days = [];
  
  if(G.dateView === 'week'){
    // Last 7 days counting backwards from actual today
    for(let i=0; i<7; i++){
      const d = new Date(actualToday);
      d.setDate(d.getDate() - i);
      days.push(yyyymmdd(d));
    }
    return days;
  }
  
  // This month counting backwards from actual today to the 1st
  const firstDay = new Date(actualToday.getFullYear(), actualToday.getMonth(), 1);
  for(let d = new Date(actualToday); d >= firstDay; d.setDate(d.getDate()-1)){
    days.push(yyyymmdd(new Date(d)));
  }
  return days;
}

function getFilteredCodes(){
  // Collect expected codes mappings along with their earliest expected start date
  const codes = new Map(); // code -> { sheets: [...], start: 'YYYYMMDD' }
  
  for(const sheetName of G.activeSheets){
    const sheet = G.sheets[sheetName];
    if(!sheet || sheet.error) continue;
    
    // Evaluate dict of { code -> startDate }
    for(const [code, startDate] of Object.entries(sheet.codes)){
      // Apply type filter
      if(G.activeTypes.size > 0 && !G.activeTypes.has(code[0])) continue;
      // Apply search
      if(G.searchText && !code.toLowerCase().includes(G.searchText)) continue;
      
      if(!codes.has(code)) codes.set(code, { sheets: [], start: startDate });
      codes.get(code).sheets.push(sheetName);
      
      // Override start date to smallest one if appearing in multiple sheets
      if(startDate < codes.get(code).start) {
          codes.get(code).start = startDate;
      }
    }
  }
  return codes;
}

/* ── Load data ── */
async function loadData(){
  document.getElementById('loading').style.display = 'block';
  document.getElementById('app').style.display = 'none';
  document.getElementById('error-area').innerHTML = '';
  document.getElementById('refresh-btn').classList.add('spin');
  try{
    const res = await fetch('/api/files');
    const data = await res.json();
    document.getElementById('refresh-btn').classList.remove('spin');
    document.getElementById('loading').style.display = 'none';
    if(data.error){
      document.getElementById('error-area').innerHTML = `<div class="err-card">⚠ ${data.error}</div>`;
      return;
    }
    G.sheets       = data.sheets;
    G.byDate       = data.by_date;
    G.todayStr     = data.today_str;
    G.allFileTypes = data.all_file_types;

    // Init type filters
    G.activeTypes = new Set(G.allFileTypes);

    const totalCodesSet = new Set();
    Object.values(G.sheets).forEach(sheet => {
      if(!sheet.error && sheet.codes) {
        Object.keys(sheet.codes).forEach(c => totalCodesSet.add(c));
      }
    });
    const totalFiles = Object.values(G.byDate).reduce((s,d) => s + Object.values(d).reduce((a,b)=>a+b.length,0), 0);
    const now = new Date();
    document.getElementById('h-codes').innerHTML = `<b>${totalCodesSet.size}</b> Master Codes`;
    document.getElementById('h-files').innerHTML = `<b>${totalFiles}</b> Total Files`;
    document.getElementById('h-refresh').innerHTML = `Refreshed ${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`;

    buildFilters();
    document.getElementById('app').style.display = 'block';
    render();
  } catch(e){
    document.getElementById('refresh-btn').classList.remove('spin');
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error-area').innerHTML = `<div class="err-card">Cannot reach server. Make sure server_v2.py is running.</div>`;
  }
}

/* ── Filters ── */
function buildFilters(){
  // Sheet chips
  const sfEl = document.getElementById('sheet-filter');
  sfEl.innerHTML = SHEET_NAMES.map(s => {
    const cls = `chip sheet-${s.replace(' ','_')} active`;
    return `<button class="${cls}" data-sheet="${s}" onclick="toggleSheet('${s}')">${s}</button>`;
  }).join('');

  // Type chips
  const tfEl = document.getElementById('type-filter');
  tfEl.innerHTML = G.allFileTypes.map(t => `
    <button class="chip active" data-type="${t}" onclick="toggleType('${t}')">Type ${t}</button>
  `).join('');
}

function toggleSheet(name){
  if(G.activeSheets.has(name)){
    if(G.activeSheets.size > 1) G.activeSheets.delete(name);
  } else G.activeSheets.add(name);
  document.querySelectorAll('[data-sheet]').forEach(el => {
    const n = el.dataset.sheet;
    const key = `sheet-${n.replace(' ','_')}`;
    el.className = `chip ${key}` + (G.activeSheets.has(n) ? ' active' : '');
  });
  render();
}
function toggleType(t){
  if(G.activeTypes.has(t)) { if(G.activeTypes.size>1) G.activeTypes.delete(t); } else G.activeTypes.add(t);
  document.querySelectorAll('[data-type]').forEach(el => {
    el.className = 'chip' + (G.activeTypes.has(el.dataset.type) ? ' active' : '');
  });
  render();
}
function applyFilters(){
  G.searchText = document.getElementById('search-input').value.toLowerCase();
  render();
}

/* ── View switching ── */
function setView(v){
  G.view = v;
  document.getElementById('vt-overview').className = v==='overview' ? 'vt active' : 'vt';
  document.getElementById('vt-detail').className   = v==='detail'   ? 'vt active' : 'vt';
  document.getElementById('view-overview').style.display = v==='overview' ? 'block' : 'none';
  document.getElementById('view-detail').style.display   = v==='detail'   ? 'block' : 'none';
  render();
}
function setDateView(dv){
  G.dateView = dv;
  G.expandedDays.clear();
  document.getElementById('dt-today').className = dv==='today' ? 'dt-btn active' : 'dt-btn';
  document.getElementById('dt-week').className  = dv==='week' ? 'dt-btn active' : 'dt-btn';
  document.getElementById('dt-month').className = dv==='month' ? 'dt-btn active' : 'dt-btn';
  render();
}

/* ── Main render ── */
function render(){
  if(G.view === 'overview') renderOverview();
  else renderDetail();
}

/* ── Overview ── */
function renderOverview(){
  const el = document.getElementById('view-overview');
  const days = getActiveDays();

  // Summary stats row
  let totalExp = 0, totalPres = 0;
  const codes = getFilteredCodes();
  
  days.forEach(d => {
    const dm = G.byDate[d] || {};
    codes.forEach((info, code) => {
      // ONLY check if it's currently on/after the code's valid start date!
      if (d >= info.start) {
          totalExp++;
          if(dm[code]) totalPres++;
      }
    });
  });
  
  const totalMiss = totalExp - totalPres;
  const pct = totalExp ? Math.round(totalPres/totalExp*100) : 100;
  const pctClass = pct>=95?'pct-green':pct>=70?'pct-yellow':'pct-red';

  let dateDisplay = G.dateView==='today' ? fmtDate(days[0]).short : fmtDate(days[days.length-1]).short+' – '+fmtDate(days[0]).short;

  let html = `<div class="sum-row">
    <div class="sum-pill"><div class="sp-lbl">Overall Coverage</div><div class="sp-val ${pctClass}">${pct}%</div><div class="sp-sub">${totalPres} / ${totalExp} files</div></div>
    <div class="sum-pill"><div class="sp-lbl">Missing Files</div><div class="sp-val ${totalMiss>0?'pct-red':'pct-green'}">${totalMiss}</div><div class="sp-sub">across ${days.length} day(s)</div></div>
    <div class="sum-pill"><div class="sp-lbl">Active Codes</div><div class="sp-val" style="color:var(--blue)">${codes.size}</div><div class="sp-sub">from ${G.activeSheets.size} sheet(s)</div></div>
    <div class="sum-pill"><div class="sp-lbl">Date Range</div><div class="sp-val" style="font-size:16px;padding-top:4px">${dateDisplay}</div></div>
  </div>`;

  // Per-sheet overview cards
  html += `<div class="ov-grid">`;
  for(const sheetName of SHEET_NAMES){
    if(!G.activeSheets.has(sheetName)) continue;
    const sheet = G.sheets[sheetName];
    const colorKey = sheetName.replace(' ','_');
    if(!sheet || sheet.error){
      html += `<div class="ov-card ${colorKey}"><div class="ov-name">${sheetName}</div><div style="color:var(--red);font-size:13px">${sheet?.error||'No data'}</div></div>`;
      continue;
    }

    // Transform into object array to map dates filtering
    const sheetCodes = Object.entries(sheet.codes).map(([c, start]) => ({code: c, start})).filter(cObj => {
      if(G.activeTypes.size > 0 && !G.activeTypes.has(cObj.code[0])) return false;
      if(G.searchText && !cObj.code.toLowerCase().includes(G.searchText)) return false;
      return true;
    });

    let sExp = 0, sPres = 0;
    days.forEach(d => {
      const dm = G.byDate[d] || {};
      sheetCodes.forEach(cObj => { 
        if (d >= cObj.start) {
          sExp++; 
          if(dm[cObj.code]) sPres++; 
        }
      });
    });
    
    const sMiss = sExp - sPres;
    const sPct = sExp ? Math.round(sPres/sExp*100) : 100;
    const sPctClass = sPct>=95?'pct-green':sPct>=70?'pct-yellow':'pct-red';
    const color = SHEET_COLORS[sheetName] || '#58a6ff';

    html += `<div class="ov-card ${colorKey}" onclick="drillSheet('${sheetName}')">
      <div class="ov-name">${sheetName}</div>
      <div class="ov-pct ${sPctClass}">${sPct}%</div>
      <div class="ov-sub">${sPres} found · ${sMiss} missing · ${sheetCodes.length} codes</div>
      <div class="ov-pbar"><div class="ov-pbar-fill" style="width:${sPct}%;background:${color}"></div></div>
      <div class="ov-counts">
        <span class="ov-count"><span class="dot" style="background:var(--green)"></span>${sPres} present</span>
        <span class="ov-count"><span class="dot" style="background:var(--red)"></span>${sMiss} missing</span>
        <span class="ov-count" style="margin-left:auto;color:var(--text3);font-size:11px">Click to detail →</span>
      </div>
    </div>`;
  }
  html += `</div>`;

  // Breakdown tables
  if(G.dateView === 'today'){
    html += renderTodayTable(days[0]);
  } else {
    html += renderMonthSummary(days);
  }

  el.innerHTML = html;
}

function drillSheet(sheetName){
  G.activeSheets = new Set([sheetName]);
  document.querySelectorAll('[data-sheet]').forEach(el => {
    const n = el.dataset.sheet;
    const key = `sheet-${n.replace(' ','_')}`;
    el.className = `chip ${key}` + (G.activeSheets.has(n) ? ' active' : '');
  });
  setView('detail');
}

function renderTodayTable(dayStr){
  const dm = G.byDate[dayStr] || {};
  const codes = getFilteredCodes();

  let html = '';
  for(const sheetName of SHEET_NAMES){
    if(!G.activeSheets.has(sheetName)) continue;
    const sheet = G.sheets[sheetName];
    if(!sheet || sheet.error) continue;

    // Find codes that are officially expected today (dayStr >= start_date)
    const sheetCodes = Object.keys(sheet.codes).filter(c => codes.has(c));
    const expectedToday = sheetCodes.filter(c => dayStr >= sheet.codes[c]);
    
    if(!expectedToday.length) continue;

    const present = expectedToday.filter(c => dm[c]);
    const missing = expectedToday.filter(c => !dm[c]);

    html += `<div class="detail-card" style="margin-bottom:14px">
      <div class="detail-header">
        <h3>${sheetName}</h3>
        <span class="dh-meta">${present.length} present · ${missing.length} missing</span>
      </div>
      <div style="padding:14px 20px">
        ${missing.length?`<div class="sec-head">Missing <span class="sec-count">${missing.length}</span></div>
        <div class="files-grid-inner" style="margin-bottom:14px">
          ${missing.map(c => `<div class="fchip fchip-miss">
            <span class="fchip-icon">✗</span>
            <div><div class="fchip-name">${getExpectedFileName(c, dayStr)}</div><div class="fchip-meta">Missing</div></div>
          </div>`).join('')}
        </div>`:''}
        ${present.length?`<div class="sec-head">Present <span class="sec-count">${present.length}</span></div>
        <div class="files-grid-inner">
          ${present.map(c => {
            const f = (dm[c]||[])[0];
            return `<div class="fchip fchip-ok">
              <span class="fchip-icon">✓</span>
              <div><div class="fchip-name">${f?f.name:c}</div><div class="fchip-meta">${fmtTime(f?.mtime)}</div></div>
            </div>`;
          }).join('')}
        </div>`:''}
      </div>
    </div>`;
  }
  return html || `<div class="empty">No data for the selected date.</div>`;
}

function renderMonthSummary(days){
  let title = G.dateView==='week' ? 'Daily Breakdown — Last 7 Days' : 'Daily Breakdown — This Month';
  let html = `<div class="detail-card"><div class="detail-header"><h3>${title}</h3></div>`;
  const codes = getFilteredCodes();

  days.forEach(ds => {
    const dm = G.byDate[ds] || {};
    let exp = 0, pres = 0;
    
    codes.forEach((info, c) => { 
      if (ds >= info.start) {
        exp++;
        if(dm[c]) pres++; 
      }
    });
    
    const miss = exp - pres;
    const pct = exp ? Math.round(pres/exp*100) : 100;
    const color = pct>=95?'var(--green)':pct>=70?'var(--yellow)':'var(--red)';
    const isExp = G.expandedDays.has(ds);

    html += `<div class="day-section">
      <div class="day-row ${isExp?'expanded':''}" onclick="toggleDay('${ds}')">
        <span class="dr-date">${fmtDate(ds).iso}</span>
        <span class="dr-day">${fmtDate(ds).day}</span>
        <div class="dr-bar"><div class="dr-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="dr-pct" style="color:${color}">${pct}%</span>
        <div class="dr-counts">
          <span class="dr-count"><span class="dot" style="width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--green)"></span>${pres}</span>
          <span class="dr-count"><span class="dot" style="width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--red)"></span>${miss}</span>
        </div>
        <svg class="dr-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
      </div>
      <div class="day-files ${isExp?'open':''}" id="files-${ds}">
        ${isExp ? renderDayFiles(ds, codes) : ''}
      </div>
    </div>`;
  });
  html += `</div>`;
  return html;
}

function renderDayFiles(ds, codes){
  const dm = G.byDate[ds] || {};
  let phtml = '', mhtml = '';
  codes.forEach((info, c) => {
    // Make sure we only flag expected ones
    if (ds >= info.start) {
        const sheetLabel = info.sheets.map(s => `<span class="sheet-pill sp-${s.replace(' ','_')}">${s}</span>`).join('');
        if(dm[c]){
          const f = dm[c][0];
          phtml += `<div class="fchip fchip-ok">
            <span class="fchip-icon">✓</span>
            <div><div class="fchip-name">${f.name}${sheetLabel}</div><div class="fchip-meta">${fmtTime(f.mtime)}</div></div>
          </div>`;
        } else {
          mhtml += `<div class="fchip fchip-miss">
            <span class="fchip-icon">✗</span>
            <div><div class="fchip-name">${getExpectedFileName(c, ds)}${sheetLabel}</div><div class="fchip-meta">Missing</div></div>
          </div>`;
        }
    }
  });
  
  let html = '';
  if(mhtml) html += `<div class="sec-head">Missing</div><div class="files-grid-inner" style="margin-bottom:10px">${mhtml}</div>`;
  if(phtml) html += `<div class="sec-head">Present</div><div class="files-grid-inner">${phtml}</div>`;
  return html || '<div style="color:var(--text3);font-size:13px;padding:8px 0">No files tracked for this date yet.</div>';
}

function toggleDay(ds){
  if(G.expandedDays.has(ds)) G.expandedDays.delete(ds);
  else G.expandedDays.add(ds);
  render();
}

/* ── Detail view ── */
function renderDetail(){
  const el = document.getElementById('view-detail');
  const days = getActiveDays();
  const codes = getFilteredCodes();

  let titleStr = G.dateView==='today'?'Today':(G.dateView==='week'?'Last 7 Days':'This Month');

  let html = `<div class="detail-card">
    <div class="detail-header">
      <h3>Daily Detail — ${titleStr}</h3>
      <span class="dh-meta">${codes.size} codes · ${days.length} day(s)</span>
    </div>`;

  days.forEach(ds => {
    const dm = G.byDate[ds] || {};
    let exp = 0, pres = 0;
    
    codes.forEach((info, c) => { 
      if (ds >= info.start) {
        exp++; 
        if(dm[c]) pres++; 
      }
    });
    
    const miss = exp - pres;
    const pct = exp ? Math.round(pres/exp*100) : 100;
    const color = pct>=95?'var(--green)':pct>=70?'var(--yellow)':'var(--red)';
    const isExp = G.expandedDays.has(ds);

    html += `<div class="day-section">
      <div class="day-row ${isExp?'expanded':''}" onclick="toggleDay('${ds}')">
        <span class="dr-date">${fmtDate(ds).iso}</span>
        <span class="dr-day">${fmtDate(ds).day}</span>
        <div class="dr-bar"><div class="dr-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="dr-pct" style="color:${color}">${pct}%</span>
        <div class="dr-counts">
          <span class="dr-count"><span class="dot" style="width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--green)"></span>${pres} found</span>
          <span class="dr-count"><span class="dot" style="width:7px;height:7px;border-radius:50%;display:inline-block;background:var(--red)"></span>${miss} missing</span>
        </div>
        <svg class="dr-chev" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
      </div>
      <div class="day-files ${isExp?'open':''}" id="files-${ds}">
        ${isExp ? renderDayFilesGrouped(ds, codes) : ''}
      </div>
    </div>`;
  });

  html += `</div>`;
  el.innerHTML = html;
}

function renderDayFilesGrouped(ds, codes){
  const dm = G.byDate[ds] || {};
  let html = '';

  for(const sheetName of SHEET_NAMES){
    if(!G.activeSheets.has(sheetName)) continue;
    const sheet = G.sheets[sheetName];
    if(!sheet || sheet.error) continue;
    const color = SHEET_COLORS[sheetName] || '#58a6ff';

    const sheetCodes = Object.keys(sheet.codes).filter(c => codes.has(c));
    const expectedToday = sheetCodes.filter(c => ds >= sheet.codes[c]);
    
    if(!expectedToday.length) continue;

    const present = expectedToday.filter(c => dm[c]);
    const missing = expectedToday.filter(c => !dm[c]);

    html += `<div style="margin-bottom:14px">
      <div class="sec-head" style="color:${color}">${sheetName} <span class="sec-count">${present.length}/${expectedToday.length}</span></div>
      <div class="files-grid-inner">
        ${missing.map(c => `<div class="fchip fchip-miss">
          <span class="fchip-icon">✗</span>
          <div><div class="fchip-name">${getExpectedFileName(c, ds)}</div><div class="fchip-meta">Missing</div></div>
        </div>`).join('')}
        ${present.map(c => {
          const f = (dm[c]||[])[0];
          return `<div class="fchip fchip-ok">
            <span class="fchip-icon">✓</span>
            <div><div class="fchip-name">${f?f.name:c}</div><div class="fchip-meta">${fmtTime(f?.mtime)}</div></div>
          </div>`;
        }).join('')}
      </div>
    </div>`;
  }
  return html || '<div style="color:var(--text3);font-size:13px">No expected files for this date yet.</div>';
}

/* ── CSV Export ── */
function downloadCSV(){
  const days = getActiveDays();
  const codes = getFilteredCodes();
  let csv = 'Date,Code,FileType,SheetName,Status,Filename,ReceivedAt\n';
  [...days].reverse().forEach(ds => {
    const dm = G.byDate[ds] || {};
    codes.forEach((info, code) => {
      if (ds >= info.start) {
        const files = dm[code] || [];
        if(files.length){
          files.forEach(f => {
            csv += `${fmtDate(ds).iso},${code},${code[0]},"${info.sheets.join('|')}",PRESENT,${f.name},${fmtTime(f.mtime)}\n`;
          });
        } else {
          // Add the precise expected filename to the missing row!
          csv += `${fmtDate(ds).iso},${code},${code[0]},"${info.sheets.join('|')}",MISSING,${getExpectedFileName(code, ds)},\n`;
        }
      }
    });
  });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
  a.download = `FileMonitor_Report_${G.todayStr}.csv`;
  a.click();
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
        pass

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
    print("=" * 65)
    print("  File Monitor V2.1 — 5-Sheet Comparison Edition")
    print(f"  Watch File   : {WATCH_FILE}")
    for name, path in SHEETS.items():
        exists = "✓" if os.path.isfile(path) else "✗ NOT FOUND"
        print(f"  {name:<16}: {path}  [{exists}]")
    print(f"  Server       : http://localhost:{PORT}")
    print("  Press Ctrl+C to stop.")
    print("=" * 65)
    server = HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")