#!/usr/bin/env python3
"""Recorta os dias futuros do SVG gerado por yoshi389111/github-profile-3d-contrib.

A action sempre desenha o ano-calendario cheio (jan-dez); os dias depois de
hoje aparecem como slabs cinzas no final. Este script remove esses grupos
<g> e ajusta o periodo "AAAA-MM-DD / AAAA-MM-DD" para terminar hoje.

Idempotente: rodar 2x nao muda nada na segunda vez. So remove barras planas
(nivel 0) cuja data reconstruida pela geometria e' posterior a hoje, entao
dias passados sem contribuicao sao preservados.

Uso:
    python3 .github/scripts/trim-future.py --year 2026 profile-3d-contrib
"""

import argparse
import math
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo

    TODAY = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
except Exception:
    TODAY = date.today()

# Mesmas constantes de src/create-svg.ts e src/create-3d-contrib.ts
WIDTH, HEIGHT = 1280, 850
ANGLE_TAN = math.tan(math.radians(30))
FLAT_HEIGHT = 3.0  # calHeight de um dia com 0 contribuicoes

# Apenas os grupos das barras usam translate(x y) com espaco (sem virgula).
BAR_RE = re.compile(r'<g transform="translate\(([0-9.]+) ([0-9.]+)\)">(.*?)</g>', re.DOTALL)
PERIOD_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) / (\d{4}-\d{2}-\d{2})")


def js_dow(d: date) -> int:
    """Dia da semana no padrao JS getUTCDay(): dom=0 .. sab=6."""
    return (d.weekday() + 1) % 7


def process_file(svg_path: Path, year: int) -> tuple[int, bool]:
    text = svg_path.read_text(encoding="utf-8")

    first = date(year, 1, 1)
    leading = js_dow(first)
    sunday_first = first - timedelta(days=leading)
    total_days = (date(year + 1, 1, 1) - first).days
    weekcount = math.ceil((total_days + leading) / 7.0)

    dx = WIDTH / 64
    dy = dx * ANGLE_TAN
    offset_x = dx * 7
    offset_y = HEIGHT - (weekcount + 7) * dy

    removed = 0

    def keep_or_drop(m: re.Match) -> str:
        nonlocal removed
        tx, ty = float(m.group(1)), float(m.group(2))
        # Assume barra plana (dias futuros sempre tem 0 contribuicoes, logo
        # calHeight == 3). Se for uma barra alta do passado, a conta abaixo
        # resulta numa data mais antiga (nunca futura), entao ela e' mantida.
        # Isso funciona para todos os templates (normal/season/rainbow/bitmap).
        base_y = ty + FLAT_HEIGHT
        a = (tx - offset_x) / dx
        b = (base_y - offset_y) / dy
        week_f, dow_f = (a + b) / 2.0, (b - a) / 2.0
        week, dow = round(week_f), round(dow_f)
        if abs(week_f - week) > 0.06 or abs(dow_f - dow) > 0.06:
            return m.group(0)  # geometria inesperada: nao toca
        if not (0 <= dow <= 6):
            return m.group(0)
        day = sunday_first + timedelta(days=week * 7 + dow)
        if day > TODAY:
            removed += 1
            return ""
        return m.group(0)

    new_text = BAR_RE.sub(keep_or_drop, text)

    period_updated = False

    def fix_period(m: re.Match) -> str:
        nonlocal period_updated
        start_s, end_s = m.group(1), m.group(2)
        end = date.fromisoformat(end_s)
        new_end = min(end, TODAY)
        if new_end != end:
            period_updated = True
            return f"{start_s} / {new_end.isoformat()}"
        return m.group(0)

    new_text = PERIOD_RE.sub(fix_period, new_text)

    if new_text != text:
        svg_path.write_text(new_text, encoding="utf-8")
    return removed, period_updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("directory", type=Path)
    args = ap.parse_args()

    svgs = sorted(args.directory.glob("profile-*.svg"))
    if not svgs:
        print(f"nenhum SVG em {args.directory}", file=sys.stderr)
        return 1

    total_removed = 0
    for svg in svgs:
        removed, period = process_file(svg, args.year)
        total_removed += removed
        print(f"{svg.name}: removidas={removed} periodo_ate_hoje={period}")

    # Sanity check: o principal continua sendo XML valido.
    import xml.dom.minidom

    main_svg = args.directory / "profile-night-green.svg"
    if main_svg.exists():
        xml.dom.minidom.parse(str(main_svg))
    print(f"hoje={TODAY} total_removidas={total_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
