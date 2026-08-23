"""
Generates docs/workflow.svg and docs/workflow.png — the graded workflow
diagram. Hand-authored (not Excalidraw) so it's reproducible from code, but
hits every organiser requirement verbatim: human input point, every LLM
query, which model each node uses, what each node does, colour-coded by
executor, the TIER-0 halt branch and the N9->N8 retry loop drawn explicitly,
and a legend.
"""
from pathlib import Path

OUT_DIR = Path(__file__).parent
CANVAS_W = 2200
CANVAS_H = 2350

COLORS = {
    "gemini": "#2F6FED",      # blue
    "ollama": "#1E9E5A",      # green (cross-model verifier / decomposer)
    "python": "#6B7280",      # grey (deterministic)
    "tool": "#C77D18",        # amber (non-LLM tool)
    "human": "#E07A1F",       # orange
    "halt": "#D03A2C",        # red
    "output": "#3A3A3A",
}

BOX_W = 760
BOX_H = 120
MAIN_X = 260  # left edge of main chain
GAP_Y = 55

svg_parts: list[str] = []


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) > max_chars and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def box(x, y, w, h, fill, title, subtitle, model=None, text_color="#FFFFFF"):
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="#1a1a1a" stroke-width="2"/>',
        f'<text x="{x + 24}" y="{y + 40}" font-family="Georgia, serif" font-size="26" font-weight="700" fill="{text_color}">{esc(title)}</text>',
    ]
    ty = y + 72
    if model:
        badge_w = len(model) * 10 + 20
        parts.append(
            f'<rect x="{x + 24}" y="{ty - 22}" width="{badge_w}" height="28" rx="6" fill="#FFFFFF" fill-opacity="0.16" stroke="{text_color}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + 34}" y="{ty - 2}" font-family="Consolas, monospace" font-size="16" fill="{text_color}">{esc(model)}</text>'
        )
        ty += 30
    max_chars = int((w - 48) / 8.2)
    for line in wrap_text(subtitle, max_chars):
        parts.append(f'<text x="{x + 24}" y="{ty}" font-family="Segoe UI, sans-serif" font-size="16" fill="{text_color}">{esc(line)}</text>')
        ty += 22
    return "\n".join(parts)


def arrow(x1, y1, x2, y2, color="#333333", label=None, dashed=False, curve=None, label_dx=12, label_dy=-8):
    dash = 'stroke-dasharray="10,6"' if dashed else ""
    if curve:
        path = f'<path d="M {x1} {y1} {curve}" fill="none" stroke="{color}" stroke-width="3" {dash} marker-end="url(#arrowhead-{color.strip("#")})"/>'
    else:
        path = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="3" {dash} marker-end="url(#arrowhead-{color.strip("#")})"/>'
    parts = [path]
    if label:
        lx = (x1 + x2) / 2 + label_dx
        ly = (y1 + y2) / 2 + label_dy
        parts.append(f'<text x="{lx}" y="{ly}" font-family="Segoe UI, sans-serif" font-size="15" font-style="italic" fill="{color}">{esc(label)}</text>')
    return "\n".join(parts)


def marker_defs(colors):
    defs = ["<defs>"]
    for c in colors:
        cid = c.strip("#")
        defs.append(
            f'<marker id="arrowhead-{cid}" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto">'
            f'<polygon points="0 0, 9 3, 0 6" fill="{c}"/></marker>'
        )
    defs.append("</defs>")
    return "\n".join(defs)


def build() -> str:
    cx = MAIN_X + BOX_W / 2
    y = 40

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="{{W}}" height="{{H}}" viewBox="0 0 {{W}} {{H}}">']
    parts.append('<rect x="0" y="0" width="{{W}}" height="{{H}}" fill="#FFFFFF"/>')
    parts.append(marker_defs(list(COLORS.values()) + ["#333333", "#8A5A00"]))

    # Title
    parts.append(f'<text x="{CANVAS_W/2}" y="{y+30}" font-family="Georgia, serif" font-size="34" font-weight="700" text-anchor="middle" fill="#111">VERITAS — Nine-Node Workflow</text>')
    parts.append(f'<text x="{CANVAS_W/2}" y="{y+58}" font-family="Segoe UI, sans-serif" font-size="17" text-anchor="middle" fill="#555">Refusal-aware grounded answering for low-resource languages — human input, every LLM query, model, and action</text>')
    y += 100

    # Human input
    hx, hy = MAIN_X, y
    parts.append(box(hx, hy, BOX_W, 90, COLORS["human"], "H1 · Human Input", "Question in Nepali / romanized Nepali / English + domain"))
    y += 90 + GAP_Y

    nodes = [
        ("N1", "Language & Intent Normalizer", "Detects language, normalizes to Devanagari + canonical English, flags ambiguities", "gemini-2.5-flash", "gemini"),
        ("N2", "Risk Tier Gate", "Classifies TIER_0 / TIER_1 / TIER_2 risk", "gemini-2.5-flash", "gemini"),
        ("N3", "Claim Decomposer", "Splits question into 2–6 atomic, independently verifiable claims", "gpt-oss:120b (Ollama Cloud)", "ollama"),
        ("N4", "Evidence Retrieval", "Site-restricted search + scrape over whitelisted domains, per claim. Not an LLM.", "Firecrawl (tool)", "tool"),
        ("N5", "Grounded Answerer", "Answers each claim from evidence only; numeric grounding enforced in code", "gemini-2.5-flash", "gemini"),
        ("N6", "Adversarial Verifier", "A DIFFERENT model family tries to falsify each claim's answer", "gpt-oss:120b (Ollama Cloud)", "ollama"),
        ("N7", "Refusal Arbiter", "ANSWER / PARTIAL_ANSWER / REFUSE — deterministic rules, no LLM, unit-tested", "deterministic Python", "python"),
        ("N8", "Synthesizer", "Composes final response in user's language from verified claims only", "gemini-2.5-flash", "gemini"),
        ("N9", "Back-Translation Fidelity Check", "Translates answer back to English to catch drift; one retry on failure", "gemini-2.5-flash", "gemini"),
    ]

    positions = {}
    prev_bottom = (cx, hy + 90)
    n2_pos = None
    n8_pos = None
    n9_pos = None

    for nid, title, subtitle, model, color_key in nodes:
        bx, by = MAIN_X, y
        parts.append(box(bx, by, BOX_W, BOX_H, COLORS[color_key], f"{nid} · {title}", subtitle, model=model))
        positions[nid] = (bx, by, BOX_W, BOX_H)
        parts.append(arrow(prev_bottom[0], prev_bottom[1], cx, by, color="#333333"))
        prev_bottom = (cx, by + BOX_H)
        if nid == "N2":
            n2_pos = (bx, by)
        if nid == "N8":
            n8_pos = (bx, by)
        if nid == "N9":
            n9_pos = (bx, by)
        y += BOX_H + GAP_Y

    # Output box
    out_x, out_y = MAIN_X, y
    parts.append(box(out_x, out_y, BOX_W, 100, COLORS["output"],
                      "OUTPUT", "Answer + citations + confidence + UNVERIFIED section (+ escalation card if TIER-0)"))
    parts.append(arrow(cx, prev_bottom[1], cx, out_y, color="#333333"))

    # TIER-0 halt branch (from N2, to the right, red, joins near output via the far-right edge
    # so the connector never crosses the legend placed below the output box)
    halt_x = MAIN_X + BOX_W + 140
    halt_y = n2_pos[1] + 10
    halt_w, halt_h = 620, 150
    parts.append(box(halt_x, halt_y, halt_w, halt_h, COLORS["halt"],
                      "HALT · TIER_0 Emergency",
                      "Escalation card: nearest emergency numbers, the danger signals detected, 'seek immediate in-person care'. No informational answer is attempted."))
    n2_right = (n2_pos[0] + BOX_W, n2_pos[1] + BOX_H / 2)
    parts.append(arrow(n2_right[0], n2_right[1], halt_x, halt_y + 70, color=COLORS["halt"], label="TIER_0",
                        curve=f"L {halt_x - 60} {n2_right[1]} L {halt_x} {halt_y + 70}"))

    connector_x = halt_x + halt_w + 60
    parts.append(arrow(halt_x + halt_w, halt_y + halt_h - 20, connector_x, out_y + 50, color=COLORS["halt"],
                        curve=f"L {connector_x} {halt_y + halt_h - 20} L {connector_x} {out_y + 50} L {out_x + BOX_W} {out_y + 50}"))

    # N9 -> N8 retry loop (curved arrow on the left side)
    loop_x = MAIN_X - 90
    n8_left = (n8_pos[0], n8_pos[1] + BOX_H / 2)
    n9_left = (n9_pos[0], n9_pos[1] + BOX_H / 2)
    parts.append(
        arrow(
            n9_left[0], n9_left[1], n8_left[0], n8_left[1],
            color="#8A5A00",
            label="fidelity drift → retry ×1",
            curve=f"L {loop_x} {n9_left[1]} L {loop_x} {n8_left[1]} L {n8_left[0]} {n8_left[1]}",
            label_dx=-170, label_dy=-8,
        )
    )

    # Legend — a horizontal strip below OUTPUT, clear of every arrow above it
    ly = out_y + 100 + 70
    parts.append(f'<text x="{MAIN_X}" y="{ly}" font-family="Georgia, serif" font-size="24" font-weight="700" fill="#111">Legend</text>')
    ly += 34
    legend_items = [
        ("gemini", "Gemini node (gemini-2.5-flash)"),
        ("ollama", "gpt-oss:120b via Ollama Cloud — different model family from Gemini"),
        ("tool", "Non-LLM tool (Firecrawl retrieval)"),
        ("python", "Deterministic Python (no LLM)"),
        ("human", "Human input"),
        ("halt", "Safety halt (TIER-0 emergency)"),
    ]
    col_x = [MAIN_X, MAIN_X + 900]
    for i, (key, desc) in enumerate(legend_items):
        col = i // 3
        row = i % 3
        ix, iy = col_x[col], ly + row * 42
        parts.append(f'<rect x="{ix}" y="{iy}" width="28" height="28" rx="6" fill="{COLORS[key]}"/>')
        parts.append(f'<text x="{ix+40}" y="{iy+21}" font-family="Segoe UI, sans-serif" font-size="16" fill="#222">{esc(desc)}</text>')

    caption_y = ly + 3 * 42 + 30
    parts.append(f'<text x="{MAIN_X}" y="{caption_y}" font-family="Segoe UI, sans-serif" font-size="14" font-style="italic" fill="#555">Solid arrows = control flow. The TIER-0 branch and the N9→N8 loop are the two points where this is a workflow</text>')
    parts.append(f'<text x="{MAIN_X}" y="{caption_y+22}" font-family="Segoe UI, sans-serif" font-size="14" font-style="italic" fill="#555">with real control flow, not a linear chain.</text>')

    content_bottom = caption_y + 60
    parts.append("</svg>")
    return "\n".join(parts), content_bottom


def main() -> None:
    svg, content_bottom = build()
    final_h = max(CANVAS_H, int(content_bottom) + 40)
    svg = svg.replace("{{W}}", str(CANVAS_W)).replace("{{H}}", str(final_h))
    svg_path = OUT_DIR / "workflow.svg"
    svg_path.write_text(svg, encoding="utf-8")
    print(f"Wrote {svg_path}")

    import cairosvg

    png_path = OUT_DIR / "workflow.png"
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=CANVAS_W)
    print(f"Wrote {png_path} ({CANVAS_W}px wide)")


if __name__ == "__main__":
    main()
