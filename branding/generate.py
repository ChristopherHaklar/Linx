"""Generate Linx logo.svg and banner.svg. Render to PNG with:
  rsvg-convert -w 1024 -h 1024 logo.svg -o logo.png
  rsvg-convert -w 1500 -h 600 banner.svg -o banner.png
Banner text is converted to paths so the SVG looks right without the fonts. Generating it needs
Bricolage Grotesque and JetBrains Mono installed (found with fc-match; variable or static files)
and fontTools."""
import functools, math, pathlib, subprocess
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
OUT = pathlib.Path(__file__).parent

@functools.cache
def load_font(family, **axes):
    """The installed font for `family`, pinned to `axes` if it's a variable font."""
    path = subprocess.run(["fc-match", "-f", "%{file}", family], capture_output=True, text=True, check=True).stdout
    font = TTFont(path)
    if family.split(":")[0].lower() not in font["name"].getBestFamilyName().lower():
        raise SystemExit(f"{family} is not installed (fc-match gave {path})")
    if "fvar" in font:
        font = instancer.instantiateVariableFont(font, {a.axisTag: axes.get(a.axisTag, a.defaultValue)
                                                         for a in font["fvar"].axes})
    return font

def text_path(text, font, size, x, y, fill, spacing=0):
    """`text` as one <path> with its baseline at y. Returns the path and the x where the text ends.
    No kerning, which matches the monospace lines and is invisible in the wordmark."""
    glyphs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    k = size / font["head"].unitsPerEm
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    for ch in text:
        name = cmap[ord(ch)]
        glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, y)))
        x += hmtx[name][0] * k + spacing
    return f'<path fill="{fill}" d="{pen.getCommands()}"/>', x

def sparkle(cx, cy, r, fill, waist=0.22):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * waist
        pts.append(f"{cx + rr*math.cos(a):.1f},{cy + rr*math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="{fill}"/>'

def link_L(color, sw=52, gap=12, dx=0, dy=0, uid="a"):
    """Two interlocked capsules arranged as an L, overlapping at the corner: the stem's rounded bottom
    and the foot's rounded left end each pass through the other, offset diagonally by `off`.
    The stroke is kept heavy so the links still read at avatar size."""
    r, off = 80, 56
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
    # The crossings sit on opposite sides of the diagonal x - y = c through the overlap's centre, so
    # each gap is cut within its own half-plane. Round zones left slivers once the stroke got heavy.
    c = mid[0] - mid[1]
    line = f"-1000,{-1000 - c} 3000,{3000 - c}"
    return f'''
  <defs>
    <clipPath id="{uid}c1"><polygon points="{line} 5000,{-1000 - c}"/></clipPath>
    <clipPath id="{uid}c2"><polygon points="{line} -3000,{3000 - c}"/></clipPath>
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

def mono(x, y, size, parts):
    font, out = load_font("JetBrains Mono", wght=500), []
    for text, color in parts:
        path, x = text_path(text, font, size, x, y, color)
        out.append(path)
    return "".join(out)

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
  {text_path("Linx", load_font("Bricolage Grotesque", opsz=12, wdth=100, wght=800), 230, x0-8, 300, word, -8)[0]}
  {mono(x0, y1, fs, [(l1a, dim), (l1b, bad)])}
  {strike(x0 + len(l1a)*cw, x0 + (len(l1a)+len(l1b))*cw, y1-11, bad)}
  {mono(x0, y2, fs, [(l2a, bad), (l2b, accent), (l2c, dim)])}
  {strike(x0, x0 + len(l2a)*cw, y2-11, bad)}
</svg>'''

a_banner = banner(INK, INK2, PAPER, MINT, "#8FA6B8", CORAL, MINT,
                  link_L(MINT, dx=30, uid="gh"),
                  extra=sparkle(1330, 150, 38, MINT) + sparkle(1385, 205, 14, PAPER))

OUT.mkdir(exist_ok=True)
for name, svg in [("logo", a_logo), ("banner", a_banner)]:
    (OUT / f"{name}.svg").write_text(svg)
