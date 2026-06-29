from __future__ import annotations

import cgi
import html
import os
import shutil
import subprocess
import sys
import traceback
import uuid
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import urlopen

from overlay_tz_dlmc_area import (
    PROJECT_DIR,
    SCRIPT_DIR,
    build_output_prefix,
    require_dependencies,
    run_analysis,
    safe_name_part,
)


HOST = "127.0.0.1"
PORT = 8765
OUTPUT_ROOT = SCRIPT_DIR / "Output"
WEB_RUN_ROOT = OUTPUT_ROOT / "web_runs"
UPLOAD_ROOT = SCRIPT_DIR / "_uploads"


def open_browser(url: str) -> None:
    if sys.platform.startswith("win"):
        try:
            os.startfile(url)
            return
        except OSError:
            pass

        try:
            subprocess.Popen(["rundll32", "url.dll,FileProtocolHandler", url])
            return
        except Exception:
            pass

    try:
        if webbrowser.open(url, new=2):
            return
    except Exception:
        pass

    if sys.platform.startswith("win"):
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
        except Exception:
            pass


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>土种地类面积统计</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172018;
      --muted: #5f6b61;
      --line: #d8ded7;
      --panel: #f7f9f6;
      --accent: #2f6f4e;
      --accent-2: #1d4f6f;
      --warn: #8a5b10;
      --bg: #eef2ec;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
    }
    main {
      width: min(1120px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 28px 0 36px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 20px;
      margin-bottom: 18px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 16px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 26px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .subtitle {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }
    .unit {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 6px;
      padding: 8px 12px;
      font-weight: 600;
      white-space: nowrap;
    }
    form {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      align-items: start;
    }
    fieldset {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 16px;
      margin: 0;
      min-width: 0;
    }
    legend {
      padding: 0 6px;
      font-weight: 700;
      color: var(--accent);
    }
    label {
      display: block;
      margin: 12px 0 6px;
      font-size: 13px;
      font-weight: 700;
      color: #2b342c;
    }
    input[type="file"],
    input[type="text"] {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: var(--panel);
      color: var(--ink);
      font-size: 14px;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      vertical-align: -3px;
      accent-color: var(--accent);
    }
    .full { grid-column: 1 / -1; }
    .actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 14px 16px;
    }
    button {
      border: 0;
      border-radius: 6px;
      background: var(--accent);
      color: #fff;
      padding: 11px 18px;
      font-size: 15px;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: #265c42; }
    .secondary {
      color: var(--muted);
      font-size: 13px;
    }
    .message {
      border-radius: 8px;
      padding: 14px 16px;
      margin-bottom: 16px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .message.error {
      border-color: #d6b279;
      background: #fff8ea;
      color: var(--warn);
    }
    .downloads {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 10px;
    }
    .downloads a {
      color: #fff;
      background: var(--accent-2);
      border-radius: 6px;
      padding: 8px 12px;
      text-decoration: none;
      font-weight: 700;
      font-size: 14px;
    }
    .hint {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    @media (max-width: 760px) {
      main { width: min(100vw - 24px, 720px); padding-top: 16px; }
      header { align-items: start; flex-direction: column; }
      form { grid-template-columns: 1fr; }
      .actions { align-items: stretch; flex-direction: column; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>土种地类面积统计</h1>
      <p class="subtitle">TZ × DLBM 二级类叠加统计</p>
    </div>
    <div class="unit">面积单位：亩；不保留小数</div>
  </header>
  {message}
  <form action="/run" method="post" enctype="multipart/form-data">
    <fieldset>
      <legend>三普土壤图</legend>
      <label for="soil_files">Shapefile 配套文件</label>
      <input id="soil_files" name="soil_files" type="file" multiple accept=".shp,.shx,.dbf,.prj,.cpg,.sbn,.sbx,.xml">
      <p class="hint">至少包含 .shp、.shx、.dbf、.prj；字段需包含 TZ。</p>
      <label for="soil_path">或填写服务器本地 .shp 路径</label>
      <input id="soil_path" name="soil_path" type="text" value="{default_soil}">
    </fieldset>

    <fieldset>
      <legend>DLTB 图斑</legend>
      <label for="dltb_files">Shapefile 配套文件</label>
      <input id="dltb_files" name="dltb_files" type="file" multiple accept=".shp,.shx,.dbf,.prj,.cpg,.sbn,.sbx,.xml">
      <p class="hint">至少包含 .shp、.shx、.dbf、.prj；字段需包含 DLBM。</p>
      <label for="dltb_path">或填写服务器本地 .shp 路径</label>
      <input id="dltb_path" name="dltb_path" type="text" value="{default_dltb}">
    </fieldset>

    <fieldset class="full">
      <legend>参数</legend>
      <label for="area_crs">面积计算坐标系</label>
      <input id="area_crs" name="area_crs" type="text" placeholder="留空则使用土壤图投影；例如 EPSG:4547">
      <label>
        <input name="save_intersection" type="checkbox" value="1">
        保存叠加面 GeoPackage
      </label>
    </fieldset>

    <div class="actions full">
      <div class="secondary">输出位置：LandDegradation\\Output\\web_runs</div>
      <button type="submit">开始统计</button>
    </div>
  </form>
</main>
</body>
</html>
"""


def render_message(kind: str = "", title: str = "", body: str = "", links: dict[str, str] | None = None) -> str:
    if not title:
        return ""

    css = "message error" if kind == "error" else "message"
    safe_title = html.escape(title)
    safe_body = html.escape(body)
    link_html = ""
    if links:
        items = []
        for label, href in links.items():
            items.append(f'<a href="{html.escape(href)}">{html.escape(label)}</a>')
        link_html = f'<div class="downloads">{"".join(items)}</div>'

    return f'<section class="{css}"><strong>{safe_title}</strong><p>{safe_body}</p>{link_html}</section>'


def index_page(message: str = "") -> bytes:
    default_soil = PROJECT_DIR / "Data" / "安国市三普土壤图.shp"
    default_dltb = PROJECT_DIR / "Data" / "安国DLTB.shp"
    page = HTML_PAGE
    page = page.replace("{message}", message)
    page = page.replace("{default_soil}", html.escape(str(default_soil)))
    page = page.replace("{default_dltb}", html.escape(str(default_dltb)))
    return page.encode("utf-8")


def field_items(form: cgi.FieldStorage, name: str) -> list[cgi.FieldStorage]:
    if name not in form:
        return []
    value = form[name]
    if isinstance(value, list):
        return value
    return [value]


def safe_filename(filename: str) -> str:
    name = Path(filename).name.replace("\x00", "").strip()
    if not name:
        name = f"upload_{uuid.uuid4().hex}"
    return name


def save_upload_group(form: cgi.FieldStorage, field_name: str, target_dir: Path) -> Path | None:
    target_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for item in field_items(form, field_name):
        if not getattr(item, "filename", None):
            continue

        filename = safe_filename(item.filename)
        path = target_dir / filename
        with path.open("wb") as output:
            shutil.copyfileobj(item.file, output)
        saved.append(path)

    if not saved:
        return None

    shp_files = [path for path in saved if path.suffix.lower() == ".shp"]
    if len(shp_files) != 1:
        raise ValueError(f"{field_name} 需要且只能包含一个 .shp 文件。")

    stem = shp_files[0].with_suffix("")
    missing = [suffix for suffix in [".shx", ".dbf"] if not stem.with_suffix(suffix).exists()]
    if missing:
        raise ValueError(f"{shp_files[0].name} 缺少配套文件：{', '.join(missing)}")

    return shp_files[0]


def relative_download_link(path: Path) -> str:
    relative = path.resolve().relative_to(OUTPUT_ROOT.resolve())
    return "/download?file=" + quote(str(relative).replace("\\", "/"))


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(index_page())
            return
        if parsed.path == "/download":
            self.handle_download(parsed.query)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.handle_run()

    def handle_run(self) -> None:
        try:
            require_dependencies()
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                    "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
                },
            )

            run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
            upload_dir = UPLOAD_ROOT / run_id

            soil_upload = save_upload_group(form, "soil_files", upload_dir / "soil")
            dltb_upload = save_upload_group(form, "dltb_files", upload_dir / "dltb")

            soil_path = soil_upload or Path(form.getfirst("soil_path", "")).expanduser()
            dltb_path = dltb_upload or Path(form.getfirst("dltb_path", "")).expanduser()
            dataset_label = f"{safe_name_part(soil_path, '土壤图')}__{safe_name_part(dltb_path, 'DLTB')}"
            out_dir = WEB_RUN_ROOT / f"{dataset_label}__{run_id}"
            area_crs = form.getfirst("area_crs", "").strip() or None
            save_intersection = form.getfirst("save_intersection") == "1"

            summary, outputs = run_analysis(
                soil_path=soil_path,
                dltb_path=dltb_path,
                out_dir=out_dir,
                area_crs=area_crs,
                save_intersection=save_intersection,
                prefix=build_output_prefix(soil_path, dltb_path),
            )

            links = {}
            for label, path in [
                ("CSV", outputs.get("csv")),
                ("Excel", outputs.get("xlsx")),
                ("ArcGIS制图数据库", outputs.get("arcgis_gpkg")),
                ("叠加结果GeoPackage", outputs.get("gpkg")),
            ]:
                if path:
                    links[label] = relative_download_link(path)

            message = render_message(
                title="统计完成",
                body=f"生成 {len(summary)} 条统计记录。结果目录：{out_dir}",
                links=links,
            )
            self.send_html(index_page(message))
        except Exception as exc:
            traceback.print_exc()
            message = render_message("error", "统计失败", str(exc))
            self.send_html(index_page(message), HTTPStatus.BAD_REQUEST)

    def handle_download(self, query: str) -> None:
        params = parse_qs(query)
        if "file" not in params:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return

        relative = unquote(params["file"][0])
        target = (OUTPUT_ROOT / relative).resolve()
        try:
            target.relative_to(OUTPUT_ROOT.resolve())
        except ValueError:
            self.send_error(HTTPStatus.FORBIDDEN)
            return

        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = "application/octet-stream"
        if target.suffix.lower() == ".csv":
            content_type = "text/csv; charset=utf-8"
        elif target.suffix.lower() == ".xlsx":
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(target.name)}")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, data: bytes, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        print("%s - %s" % (self.address_string(), format % args))


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    WEB_RUN_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    url = f"http://{HOST}:{PORT}/"

    try:
        with urlopen(url, timeout=1) as response:
            if response.status == 200:
                print(f"页面服务已经在运行：{url}", flush=True)
                open_browser(url)
                return
    except Exception:
        pass

    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"土种地类面积统计页面已启动：{url}", flush=True)
    open_browser(url)
    server.serve_forever()


if __name__ == "__main__":
    main()
