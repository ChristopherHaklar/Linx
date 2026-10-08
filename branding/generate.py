"""Generate Linx logo.svg and banner.svg. Render to PNG with:
  rsvg-convert -w 1024 -h 1024 logo.svg -o logo.png
  rsvg-convert -w 1500 -h 600 banner.svg -o banner.png
(needs Bricolage Grotesque and JetBrains Mono installed)"""
import math, pathlib
OUT = pathlib.Path(__file__).parent

def sparkle(cx, cy, r, fill, waist=0.22):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * waist
        pts.append(f"{cx + rr*math.cos(a):.1f},{cy + rr*math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'

def link_L(color, sw=36, gap=12, dx=0, dy=0, uid="a"):
    """Two interlocked capsules arranged as an L, overlapping at the corner: the stem's rounded bottom
    and the foot's rounded left end each pass through the other, offset diagonally by `off`.
    With r=70 and off=58 the curves cross at about 75 degrees and stay 22px apart (after stroke)
    where they run side by side."""
    r, off = 70, 58
    stem = dict(x=60+dx, y=50+dy, w=2*r, h=354, r=r)
    sc = (stem["x"] + r, stem["y"] + stem["h"] - r)        # centre of the stem's bottom curve
    fc = (sc[0] + off, sc[1] + off)                        # centre of the foot's left curve
    foot = dict(x=fc[0] - r, y=fc[1] - r, w=300, h=2*r, r=r)
    def cap(c, extra=0, col=color):
        return (f'<rect x="{c["x"]}" y="{c["y"]}" width="{c["w"]}" height="{c["h"]}" rx="{c["r"]}" '
                f'fill="none" stroke="{col}" stroke-width="{sw+extra}"/>')
    # Upper-right crossing: the stem's straight right side meets the foot's straight top. Foot goes over.
    p1 = (stem["x"] + stem["w"], foot["y"])
    # Lower-left crossing: where the two curves meet (the circle intersection below-left). Stem goes over.
    mid, k = ((sc[0] + fc[0]) / 2, (sc[1] + fc[1]) / 2), math.sqrt(r*r - off*off / 2) / math.sqrt(2)
    p2 = (round(mid[0] - k, 1), round(mid[1] + k, 1))
    # Zones around each crossing where the gap is cut. Big enough that the cut follows the upper link's
    # outline, small enough not to reach the other crossing (elsewhere the links are kept far enough apart).
    gr = 50
    return f'''
  <defs>
    <clipPath id="{uid}c1"><circle cx="{p1[0]}" cy="{p1[1]}" r="{gr}"/></clipPath>
    <clipPath id="{uid}c2"><circle cx="{p2[0]}" cy="{p2[1]}" r="{gr}"/></clipPath>
    <mask id="{uid}m1" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="2000">
      <rect width="2000" height="2000" fill="#fff"/>
      <g clip-path="url(#{uid}c1)">{cap(foot, 2*gap, "#000")}</g>
    </mask>
    <mask id="{uid}m2" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="2000">
      <rect width="2000" height="2000" fill="#fff"/>
      <g clip-path="url(#{uid}c2)">{cap(stem, 2*gap, "#000")}</g>
    </mask>
  </defs>
  <g mask="url(#{uid}m1)">{cap(stem)}</g>
  <g mask="url(#{uid}m2)">{cap(foot)}</g>'''

# ---------- Link monogram ----------
INK, INK2, MINT, CORAL, PAPER = "#0E1C2B", "#16304A", "#3EE0A1", "#FF7A6B", "#EAF4F0"

a_logo = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs><radialGradient id="g" cx="0.3" cy="0.25" r="0.9">
    <stop offset="0" stop-color="{INK2}"/><stop offset="1" stop-color="{INK}"/></radialGradient></defs>
  <rect width="512" height="512" fill="url(#g)"/>
  {link_L(MINT, dx=15)}
  {sparkle(372, 150, 46, PAPER)}
  {sparkle(410, 214, 18, MINT)}
</svg>'''

def mono(x, y, size, parts, anchor="start"):
    spans = "".join(f'<tspan fill="{c}"{" text-decoration=\"line-through\"" if s else ""}>{t.replace("&", "&amp;")}</tspan>' for t, c, s in parts)
    return (f'<text x="{x}" y="{y}" font-family="JetBrains Mono" font-weight="500" font-size="{size}" '
            f'text-anchor="{anchor}" xml:space="preserve">{spans}</text>')

def strike(x1, x2, y, color, w=4):
    return f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{color}" stroke-width="{w}" stroke-linecap="round"/>'

def banner(bg1, bg2, word, accent, dim, bad, arrow, ghost, extra=""):
    # Monospace advance for JetBrains Mono = 0.6em
    fs = 34
    cw = fs * 0.6  # JetBrains Mono advance
    x0 = 610
    l1a, l1b = "youtu.be/dQw4w9WgXcQ", "?si=Q2aF8kL0xTe"
    l2a, l2b, l2c = "x.com", " fixvx.com", "/linx/status/1840"
    y1, y2 = 400, 456
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1500 600" width="1500" height="600">
  <defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="{bg2}"/><stop offset="1" stop-color="{bg1}"/></linearGradient></defs>
  <rect width="1500" height="600" fill="url(#bg)"/>
  <g opacity="0.10" transform="translate(-60,-150) scale(1.35)">{ghost}</g>
  {extra}
  <text x="{x0-8}" y="300" font-family="Bricolage Grotesque" font-weight="800" font-size="230"
        letter-spacing="-8" fill="{word}">Linx</text>
  {mono(x0, y1, fs, [(l1a, dim, 0), (l1b, bad, 0)])}
  {strike(x0 + len(l1a)*cw, x0 + (len(l1a)+len(l1b))*cw, y1-11, bad)}
  {mono(x0, y2, fs, [(l2a, bad, 0), (l2b, accent, 0), (l2c, dim, 0)])}
  {strike(x0, x0 + len(l2a)*cw, y2-11, bad)}
</svg>'''

a_banner = banner(INK, INK2, PAPER, MINT, "#8FA6B8", CORAL, MINT,
                  link_L(MINT, dx=30, uid="gh"),
                  extra=sparkle(1330, 150, 38, MINT) + sparkle(1385, 205, 14, PAPER))

OUT.mkdir(exist_ok=True)
for name, svg in [("logo", a_logo), ("banner", a_banner)]:
    (OUT / f"{name}.svg").write_text(svg)
