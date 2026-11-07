import html, os, re, threading
from functools import lru_cache
import uharfbuzz as hb
from reportlab.lib.colors import black, toColor
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen.canvas import FILL_NON_ZERO
from reportlab.platypus import Paragraph as _RLParagraph
from reportlab.platypus.flowables import Flowable

FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts', 'JameelNooriNastaleeq.ttf')
SIZE_FACTOR = 1.55   # Nastaleeq Naskh se chhota lagta hai (visibility ke liye bara kiya)
LINE_FACTOR = 1.45   # minimum line height = fontSize * LINE_FACTOR
BASELINE = LINE_FACTOR / 2 + 0.325   # ink spans about -0.35em..+1.0em, so this centres it in the line box
SPACE_EM = 0.26      # font ki apni space ~0 chaurai ki hai
BOLD_STROKE = 0.04    # faux-bold (font mein bold nahi)
REGULAR_STROKE = 0.016  # normal text par bareek stroke, taake patli Nastaleeq lakeeren chhoti print mein saaf rahein

_lock = threading.Lock(); _hb_font = None; _upem = 2048

def _font():
    global _hb_font, _upem
    if _hb_font is None:
        with _lock:
            if _hb_font is None:
                face = hb.Face(hb.Blob.from_file_path(FONT_PATH))
                _upem = face.upem
                _hb_font = hb.Font(face)
    return _hb_font

def _upem_value():
    _font(); return _upem

class _Pen:
    def __init__(self): self.ops = []; self._cur = (0.0, 0.0)
    def moveTo(self, p): self._cur = p; self.ops.append(('M', p[0], p[1]))
    def lineTo(self, p): self._cur = p; self.ops.append(('L', p[0], p[1]))
    def curveTo(self, a, b, c): self._cur = c; self.ops.append(('C', *a, *b, *c))
    def qCurveTo(self, *pts):
        pts = list(pts); end = pts.pop()
        for i, c in enumerate(pts):
            to = ((c[0]+pts[i+1][0])/2, (c[1]+pts[i+1][1])/2) if i < len(pts)-1 else end
            x0, y0 = self._cur
            self.curveTo((x0+2/3*(c[0]-x0), y0+2/3*(c[1]-y0)),
                         (to[0]+2/3*(c[0]-to[0]), to[1]+2/3*(c[1]-to[1])), to)
    def closePath(self): self.ops.append(('Z',))
    def endPath(self): self.ops.append(('Z',))
    def addComponent(self, *a, **k): pass

@lru_cache(maxsize=None)
def _outline(gid):
    pen = _Pen(); _font().draw_glyph_with_pen(gid, pen); return tuple(pen.ops)

@lru_cache(maxsize=8192)
def _shape(text, rtl):
    buf = hb.Buffer(); buf.add_str(text)
    if rtl: buf.direction, buf.script, buf.language = 'rtl', 'Arab', 'ur'
    else:   buf.direction, buf.script, buf.language = 'ltr', 'Latn', 'en'
    hb.shape(_font(), buf, {})
    glyphs, x = [], 0
    for i, p in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append((i.codepoint, x + p.x_offset, p.y_offset)); x += p.x_advance
    return tuple(glyphs), x

ARABIC_RE = re.compile('[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
_L = 'A-Za-z0-9\u06F0-\u06F9\u0660-\u0669'
_TOKEN_RE = re.compile(
    r'(?P<space>[ \t\u00A0]+)'
    r'|(?P<ltr>[+\-]?[' + _L + r'](?:[' + _L + r'.,:/%+\-]*[' + _L + r'%])?)'
    r'|(?P<rtl>(?:(?![' + _L + r'])\S)+)')
_NORMALIZE = str.maketrans({'\u064A': '\u06CC', '\u0643': '\u06A9', '\u0649': '\u06CC'})
_TAG_RE = re.compile(r'<\s*(/?)\s*([a-zA-Z]+)([^>]*?)(/?)\s*>')
_ATTR_RE = re.compile(r'([a-zA-Z]+)\s*=\s*(?:\'([^\']*)\'|"([^"]*)"|([^\s>]+))')

class _Tok:
    __slots__ = ('kind', 'text', 'bold', 'color', 'size', 'w')
    def __init__(self, kind, text, bold, color, size):
        self.kind, self.text, self.bold, self.color, self.size, self.w = kind, text, bold, color, size, 0.0

def _parse(markup, base_color, base_size):
    state = {'bold': False, 'color': base_color, 'size': base_size}
    stack, tokens, pos = [], [], 0
    def add_text(chunk):
        chunk = html.unescape(chunk).translate(_NORMALIZE)
        raw = [[m.lastgroup, m.group()] for m in _TOKEN_RE.finditer(chunk)]
        merged, i = [], 0
        while i < len(raw):                      # LTR + space + LTR = ek chunk ("RS 1,000")
            kind, txt = raw[i]
            if kind == 'ltr':
                while i+2 < len(raw) and raw[i+1][0] == 'space' and raw[i+2][0] == 'ltr':
                    txt += raw[i+1][1] + raw[i+2][1]; i += 2
            merged.append((kind, txt)); i += 1
        for kind, txt in merged:
            tokens.append(_Tok(kind, ' ' if kind == 'space' else txt,
                               state['bold'], state['color'], state['size']))
    for m in _TAG_RE.finditer(markup):
        if m.start() > pos: add_text(markup[pos:m.start()])
        pos = m.end()
        closing, name, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if name == 'br':
            tokens.append(_Tok('br', '', False, None, base_size))
        elif name in ('b', 'strong', 'font', 'i', 'u', 'span'):
            if closing:
                if stack: state = stack.pop()
            elif not selfclose:
                stack.append(dict(state))
                if name in ('b', 'strong'): state['bold'] = True
                elif name == 'font':
                    for am in _ATTR_RE.finditer(attrs):
                        k, v = am.group(1).lower(), am.group(2) or am.group(3) or am.group(4)
                        try:
                            if k == 'color': state['color'] = toColor(v)
                            elif k == 'size': state['size'] = float(v)
                        except Exception: pass
    if pos < len(markup): add_text(markup[pos:])
    return tokens

def _measure(t):
    if t.kind in ('rtl', 'ltr'):
        t.w = _shape(t.text, t.kind == 'rtl')[1] * t.size * SIZE_FACTOR / _upem_value()
    elif t.kind == 'space':
        t.w = SPACE_EM * t.size * SIZE_FACTOR
    return t

class UrduParagraph(Flowable):
    def __init__(self, text, style, bulletText=None, **kw):
        Flowable.__init__(self)
        self.text, self.style = str(text), style
        self.spaceBefore = getattr(style, 'spaceBefore', 0) or 0
        self.spaceAfter = getattr(style, 'spaceAfter', 0) or 0
        self._lines, self._avail = [], None
        base = getattr(style, 'textColor', black) or black
        self._tokens = [_measure(t) for t in _parse(self.text, base, float(style.fontSize))]

    def _break(self, avail):
        lines, cur, curw = [], [], 0.0
        def close():
            nonlocal cur, curw
            while cur and cur[-1].kind == 'space': curw -= cur.pop().w
            lines.append((cur, max(curw, 0.0))); cur, curw = [], 0.0
        for t in self._tokens:
            if t.kind == 'br': close()
            elif t.kind == 'space':
                if cur: cur.append(t); curw += t.w
            else:
                if cur and curw + t.w > avail + 0.01: close()
                cur.append(t); curw += t.w
        if cur or not lines: close()
        return lines

    def _lh(self, line):
        size = max([t.size for t in line] or [float(self.style.fontSize)]) * SIZE_FACTOR
        return max(float(self.style.leading or 0), size * LINE_FACTOR)

    def wrap(self, availW, availH):
        self._avail = availW; self._lines = self._break(availW)
        self.width = availW; self.height = sum(self._lh(l) for l, _ in self._lines)
        return self.width, self.height

    def split(self, availW, availH): return []
    def minWidth(self): return max([t.w for t in self._tokens if t.kind != 'space'] or [0])
    def getPlainText(self, identify=None): return re.sub(r'<[^>]*>', '', self.text)

    def draw(self):
        canv, align, y_top, upem = self.canv, getattr(self.style, 'alignment', 0), self.height, _upem_value()
        for line, lw in self._lines:
            lh = self._lh(line)
            size = max([t.size for t in line] or [float(self.style.fontSize)]) * SIZE_FACTOR
            baseline = y_top - (lh - size * LINE_FACTOR) / 2 - size * BASELINE
            right = self._avail if align in (TA_RIGHT, TA_JUSTIFY) else \
                    (self._avail + lw) / 2 if align == TA_CENTER else lw
            cursor = right
            for t in line:                       # RTL: logical order right se left
                left = cursor - t.w
                if t.kind in ('rtl', 'ltr'): self._draw_token(canv, t, left, baseline, upem)
                cursor = left
            y_top -= lh

    def _draw_token(self, canv, t, left, baseline, upem):
        glyphs, _ = _shape(t.text, t.kind == 'rtl')
        sc = t.size * SIZE_FACTOR / upem
        p = canv.beginPath()
        for gid, gx, gy in glyphs:
            ox, oy = left + gx * sc, baseline + gy * sc
            for op in _outline(gid):
                if op[0] == 'M': p.moveTo(ox+op[1]*sc, oy+op[2]*sc)
                elif op[0] == 'L': p.lineTo(ox+op[1]*sc, oy+op[2]*sc)
                elif op[0] == 'C': p.curveTo(*(v for i in (1, 3, 5) for v in (ox+op[i]*sc, oy+op[i+1]*sc)))
                else: p.close()
        canv.saveState()
        color = t.color or black
        canv.setFillColor(color)
        canv.setStrokeColor(color)
        canv.setLineWidth(t.size*SIZE_FACTOR*(BOLD_STROKE if t.bold else REGULAR_STROKE)); canv.setLineJoin(1)
        canv.drawPath(p, stroke=1, fill=1, fillMode=FILL_NON_ZERO)
        canv.restoreState()

def Paragraph(text, style, bulletText=None, **kw):
    """Reportlab Paragraph ka drop-in: Urdu/Arabic ho to Nastaleeq engine, warna normal."""
    if isinstance(text, str) and ARABIC_RE.search(re.sub(r'<[^>]*>', '', text)):
        return UrduParagraph(text, style, bulletText, **kw)
    return _RLParagraph(text, style, bulletText, **kw)