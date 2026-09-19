#!/usr/bin/env python3
"""Genera profile/repos.svg con commits y ultima actividad por repositorio publico.

Solo se listan repositorios PUBLICOS del owner (la API publica no expone los privados).
Para evitar el rate-limit, el workflow pasa GITHUB_TOKEN como Bearer.
"""
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

OWNER = os.environ.get("OWNER", "FacundoChacon")
OUT = os.environ.get("OUT", "profile/repos.svg")
MAX_ROWS = 8
TIMEOUT = 30
EXCLUDED = {"arasaka-neon-wallpaper"}

HEADERS = {"User-Agent": "opencode", "Accept": "application/vnd.github+json"}
token = os.environ.get("GITHUB_TOKEN", "")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.headers


def commit_count(full_name):
    try:
        _, headers = api(f"/repos/{full_name}/commits?per_page=1")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 0
        print(f"AVISO: no se pudo contar commits de {full_name} (HTTP {exc.code})", file=sys.stderr)
        raise
    except Exception as exc:
        print(f"AVISO: no se pudo contar commits de {full_name} ({exc})", file=sys.stderr)
        raise
    link = headers.get("Link") or ""
    m = re.search(r"page=(\d+)>; rel=[\"']last[\"']", link)
    return int(m.group(1)) if m else 1


def truncate(name, limit=38):
    return name if len(name) <= limit else name[: limit - 1] + "\u2026"


def build_svg(rows, total, n_public, extra_note):
    w, row_h, title_h, head_h, foot_h = 500, 26, 46, 26, 46
    h = title_h + head_h + len(rows) * row_h + foot_h
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img">',
        "<style>"
        ".t{font:600 15px 'Segoe UI',Ubuntu,Sans-Serif;fill:#2f80ed}"
        ".hdr{font:600 12px 'Segoe UI',Ubuntu,'Helvetica Neue',Sans-Serif;fill:#586069}"
        ".cel{font:500 13px 'Segoe UI',Ubuntu,Sans-Serif;fill:#434d58}"
        ".tot{font:600 14px 'Segoe UI',Ubuntu,Sans-Serif;fill:#434d58}"
        ".note{font:400 11px 'Segoe UI',Ubuntu,Sans-Serif;fill:#8b949e}"
        "</style>",
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="6" fill="#fffefe" stroke="#e4e2e2"/>',
        f'<text class="t" x="16" y="30">Actividad por repositorio</text>',
    ]
    y = title_h + 18
    parts.append(f'<text class="hdr" x="16" y="{y}">Repositorio</text>')
    parts.append(f'<text class="hdr" x="310" y="{y}">Commits</text>')
    parts.append(f'<text class="hdr" x="398" y="{y}">Ultima actividad</text>')
    y = title_h + head_h
    for i, (name, commits, date) in enumerate(rows):
        if i % 2 == 0:
            parts.append(f'<rect x="0" y="{y - 16}" width="{w}" height="{row_h}" fill="#f6f8fa"/>')
        parts.append(f'<text class="cel" x="16" y="{y}">{html.escape(truncate(name))}</text>')
        parts.append(f'<text class="cel" x="310" y="{y}">{commits}</text>')
        parts.append(f'<text class="cel" x="398" y="{y}">{date}</text>')
        y += row_h
    parts.append(f'<text class="tot" x="16" y="{y + 8}">Total de commits: {total} en {n_public} repositorios publicos</text>')
    parts.append(f'<text class="note" x="16" y="{y + 26}">{extra_note} Los repositorios privados no se incluyen (la API publica no los expone).</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def main():
    repos, _ = api(f"/users/{OWNER}/repos?per_page=100&sort=pushed&type=public")
    public = [r for r in repos if not r.get("fork") and r["name"] not in EXCLUDED]
    rows = []
    total = 0
    for r in public:
        name = r["name"]
        n = commit_count(r["full_name"])
        total += n
        rows.append((name, n, (r.get("pushed_at") or "")[:10]))
    rows.sort(key=lambda item: item[2], reverse=True)
    rows = rows[:MAX_ROWS]
    extra_note = f"Solo se muestran los {MAX_ROWS} mas recientes." if len(rows) < len(public) else ""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(build_svg(rows, total, len(public), extra_note))
    print(f"OK {OUT}: {len(rows)} repos, {total} commits totales")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)