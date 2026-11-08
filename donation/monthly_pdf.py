"""
Monthly / annual financial statement - A4 layout.

Ye module sirf *layout* sambhalta hai (ORM ko haath nahi lagata). views.export_monthly_pdf
database se data nikaal kar plain dict/list ki shakal mein `render_monthly_pdf(ctx, background_cb)`
ko deta hai.

Mukhya khubiyan
---------------
* Page hamesha A4 (595 x 842 pt) - ab content ke hisab se page lamba nahi hota.
* Income aur Expense ab ek hi "merged ledger" mein hain:
      income  ->  us ke baad ke expenses  ->  (agli income)  -> ...
  har row par running "Balance" (bacha hua amount) update hota hai; har income-group ki
  aakhri row ka balance highlight hota hai (yani us income aur us ke expenses ke baad ka bacha hua).
* Font size khud-ba-khud itna bara chuna jata hai jitna ek A4 page mein poora aa jaye.
  Agar data itna zyada ho ke minimum readable size par bhi single page mein na aaye
  (aksar saalana report) to text chhota karne ke bajaye agla A4 page shuru ho jata hai.
* Poori A4 chorai istemal hoti hai (koi khali side nahi); imam / lease ka block bhi
  lease na ho to poori chorai le leta hai.
"""
import html
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image as RLImage, KeepInFrame, PageTemplate, Spacer, Table, TableStyle,
)

from .urdu_pdf import Paragraph

PAGE_W, PAGE_H = A4
CONTENT_W = 535                      # A4 width (595.3) minus ~30pt margin each side
MARGIN_TOP = 30
MARGIN_BOTTOM = 42                   # footer line / page number background ke liye jagah
FRAME_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
BOTTOM_MIN = 4.8                     # imam/lease sections ka sab se chhota font
BOTTOM_MAX = 7.5                     # aur sab se bara
FIT_SAFETY = 3                       # pt - rounding ki wajah se page ke kinare par na chipke

# (font size, row padding) - bara se chhota. Urdu mein asal glyph size ~1.55x hota hai
# (urdu_pdf.SIZE_FACTOR), is liye 5.6 bhi ~8.7pt Nastaleeq ke barabar hai.
def _levels(max_fs, min_fs, compact_below, max_pad=3.2, min_pad=0.8):
    """Bare se chhote font tak ka fine-grained list: (font size, row padding, compact_header)."""
    out, fs = [], max_fs
    while fs >= min_fs - 1e-9:
        t = (fs - min_fs) / (max_fs - min_fs) if max_fs > min_fs else 0
        out.append((round(fs, 2), round(min_pad + (max_pad - min_pad) * t, 2), fs <= compact_below))
        fs -= 0.1
    return out


# Urdu mein asal glyph size ~1.55x hota hai (urdu_pdf.SIZE_FACTOR): 5.6 ~ 8.7pt Nastaleeq.
LEVELS_URDU = _levels(8.5, 5.6, 6.3)
LEVELS_EN = _levels(9.0, 6.4, 6.8)

# ---- colours -------------------------------------------------------------
EMERALD = "#044e3a"
EMERALD_DARK = "#022c22"
EMERALD_MID = "#065f46"
GOLD = "#c59b27"
GOLD_LIGHT = "#fef08a"
RED_DARK = "#991b1b"
RED_DEEPER = "#7f1d1d"
INK = "#0f172a"


def _c(hex_):
    return colors.HexColor(hex_)


def esc(value):
    return html.escape("" if value is None else str(value), quote=False)


def money(value):
    return f"{value:,.0f}"


def _ps(name, font, size, color, align=0, leading=None):
    return ParagraphStyle(
        name, fontName=font, fontSize=size, leading=leading or round(size * 1.25, 2),
        textColor=_c(color) if isinstance(color, str) else color, alignment=align,
    )


class _Card(Flowable):
    """Lease ka rounded 'card' (original 3D look)."""

    def __init__(self, content, width):
        super().__init__()
        self.content, self.width, self.height = content, width, 0

    def wrap(self, aw, ah):
        _, h = self.content.wrap(self.width - 6, ah)
        self.height = h + 6
        return self.width, self.height

    def draw(self):
        c, w, h, r = self.canv, self.width, self.height, 5.0
        c.setFillColor(_c("#cbd5e1"))
        c.roundRect(2.5, -2.5, w - 2.5, h - 2.5, r, fill=1, stroke=0)
        c.setFillColor(_c("#fffdf5"))
        c.setStrokeColor(_c("#047857"))
        c.setLineWidth(1.0)
        c.roundRect(0, 0, w - 2.5, h - 2.5, r, fill=1, stroke=1)
        self.content.drawOn(c, 1.5, 1.5)


# ==========================================================================
#  Header (fixed size)
# ==========================================================================
def _build_header(ctx, compact=False):
    f, shape = ctx['fonts'], ctx['shape']
    is_urdu = ctx['is_urdu']
    font_bism, font_bold = f['bism'], f['bold']
    ur_font = f.get('urdu') or font_bism
    story = []

    p_arabic = Paragraph(shape("بِسْمِ اللهِ الرَّحْمٰنِ الرَّحِيْمِ", True),
                         _ps('bismA', font_bism, 13 if compact else 15, "#fde047", 1, 14 if compact else 17))
    p_tarjuma = Paragraph(shape("اللہ کے نام سے شروع جو بڑا مہربان نہایت رحم والا ہے", True),
                          _ps('bismT', ur_font, 8.5 if compact else 9.5, "#ffffff", 1, 10 if compact else 11))
    p_hadees = Paragraph("<b>%s</b>" % shape("بے شک جو امانت دار نہیں اس کا کوئی دین نہیں۔", True),
                         _ps('hadees', ur_font, 7.5 if compact else 8.5, "#7f1d1d", 1, 9 if compact else 10))

    hadees_box = Table([[p_hadees]], colWidths=[230])
    hadees_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _c("#fde047")),
        ('BOX', (0, 0), (-1, -1), 2.0, _c(EMERALD)),
        ('BOX', (0, 0), (-1, -1), 0.8, _c(GOLD)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1 if compact else 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 1 if compact else 2),
    ]))

    side_w = 90
    center_w = CONTENT_W - 2 * side_w
    center = Table([[[p_arabic, Spacer(1, 1), p_tarjuma]], [hadees_box]], colWidths=[center_w])
    center.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    def _img(path, h):
        """Image ko header ki poori height (h) par laata hai.

        PNG ke aas-paas ki transparent patti (jo khali jagah bana rahi thi) pehle trim
        ki jati hai, taake gumbad / kaaba green section ke upar, neeche aur bahar wali
        side ke border se chipak jayein.
        """
        if path and os.path.exists(path):
            try:
                from io import BytesIO
                from PIL import Image as PILImage
                im = PILImage.open(path).convert('RGBA')
                w0, h0 = im.size
                mask = im.getchannel('A').point(lambda v: 255 if v > 128 else 0)
                cols = list(mask.resize((w0, 1), PILImage.BOX).getdata())
                rows = list(mask.resize((1, h0), PILImage.BOX).getdata())
                thr = 255 * 0.02          # 2% se kam opaque column/row = stray pixels, ignore
                xs = [i for i, v in enumerate(cols) if v > thr]
                ys = [i for i, v in enumerate(rows) if v > thr]
                if xs and ys:
                    im = im.crop((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))
                iw, ih = im.size
                target_px = 480           # ~450 dpi at 75pt tall - print ke liye kaafi, file halki
                if ih > target_px:
                    im = im.resize((max(1, round(iw * target_px / ih)), target_px), PILImage.LANCZOS)
                    iw, ih = im.size
                buf = BytesIO()
                im.save(buf, 'PNG')
                buf.seek(0)
                return RLImage(buf, width=h * iw / ih, height=h)
            except Exception:
                pass
        return ""

    # Header row ki height wahi jo beech wale block ko chahiye (kam az kam purani fixed height).
    # Images isi poori height ko bharti hain.
    _, center_h = center.wrap(center_w, 10000)
    row_h = max(center_h + 2, 50 if compact else 68)

    box = Table([[_img(ctx.get('gumbad_path'), row_h), center, _img(ctx.get('kaaba_path'), row_h)]],
                colWidths=[side_w, center_w, side_w], rowHeights=[row_h])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _c(EMERALD_DARK)),
        ('BOX', (0, 0), (-1, -1), 2.2, _c(GOLD)),
        ('LINEABOVE', (0, 0), (-1, -1), 1.0, _c(GOLD_LIGHT)),
        ('LINEBELOW', (0, 0), (-1, -1), 1.0, _c(GOLD_LIGHT)),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'), ('ALIGN', (1, 0), (1, 0), 'CENTER'), ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # zero padding: images bahar wali side, upar aur neeche border ko touch karein
        ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (0, 0), 0), ('RIGHTPADDING', (2, 0), (2, 0), 0),
    ]))
    story += [box, Spacer(1, 3)]

    # ---- period banner
    name = ctx['month_name']
    if ctx['is_annual']:
        text = f"سالانہ مالیاتی گوشوارہ برائے {name}" if is_urdu else f"ANNUAL FINANCIAL STATEMENT — {name.upper()}"
    else:
        text = f"ماہانہ مالیاتی گوشوارہ برائے {name}" if is_urdu else f"MONTHLY FINANCIAL STATEMENT — {name.upper()}"
    banner = Table([[Paragraph("<b>%s</b>" % esc(shape(text, is_urdu)),
                               _ps('banner', font_bold, 10.5 if is_urdu else 10.0, GOLD_LIGHT, 1, 13))]],
                   colWidths=[CONTENT_W])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _c("#044e3a")),
        ('BOX', (0, 0), (-1, -1), 1.2, _c(GOLD)),
        ('LINEABOVE', (0, 0), (-1, -1), 0.6, _c(GOLD_LIGHT)), ('LINEBELOW', (0, 0), (-1, -1), 0.6, _c(GOLD_LIGHT)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
    ]))
    story += [banner, Spacer(1, 3)]

    # ---- summary cards
    net = ctx['net_balance']
    t_style = _ps('cardT', font_bold, 9.0, "#ffffff", 1, 11)
    v = lambda nm, col: _ps(nm, font_bold, 11.5, col, 1, 14)
    summary = Table([
        [Paragraph(esc(shape("کل آمدنی" if is_urdu else "TOTAL INCOME", is_urdu)), t_style),
         Paragraph(esc(shape("کل اخراجات" if is_urdu else "TOTAL EXPENSE", is_urdu)), t_style),
         Paragraph(esc(shape("ماہانہ بقایا بیلنس" if is_urdu else "NET BALANCE", is_urdu)), t_style)],
        [Paragraph(f"RS {money(ctx['total_income'])}", v('cvi', GOLD_LIGHT)),
         Paragraph(f"RS {money(ctx['total_expense'])}", v('cve', "#fee2e2")),
         Paragraph(f"RS {money(net)}", v('cvn', "#e0f2fe" if net >= 0 else "#fee2e2"))],
    ], colWidths=[178, 178, 179])
    summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 1), _c(EMERALD)),
        ('BACKGROUND', (1, 0), (1, 1), _c(RED_DARK)),
        ('BACKGROUND', (2, 0), (2, 1), _c("#0369a1") if net >= 0 else _c(RED_DARK)),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, -1), 1.2, _c(GOLD)), ('BOX', (1, 0), (1, -1), 1.2, _c("#b71c1c")),
        ('BOX', (2, 0), (2, -1), 1.2, _c("#0284c7")),
        ('LINEBELOW', (0, 0), (-1, 0), 0.8, _c(GOLD_LIGHT)),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5 if compact else 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 if compact else 2.5),
    ]))
    story += [summary, Spacer(1, 3 if compact else 4)]
    return story


# ==========================================================================
#  Merged ledger:  income -> its expenses -> (next income) ...
# ==========================================================================
def group_ledger(income_items, expense_items):
    """Har income ke saath wo expenses jo us ke baad (agli income se pehle) hue."""
    incs = sorted(income_items, key=lambda x: x['date'])
    exps = sorted(expense_items, key=lambda x: x['date'])
    groups, ei = [], 0
    lead = []
    while ei < len(exps) and (not incs or exps[ei]['date'] < incs[0]['date']):
        lead.append(exps[ei])
        ei += 1
    if lead:
        groups.append({'income': None, 'expenses': lead})
    for i, inc in enumerate(incs):
        nxt = incs[i + 1]['date'] if i + 1 < len(incs) else None
        g = {'income': inc, 'expenses': []}
        while ei < len(exps) and (nxt is None or exps[ei]['date'] < nxt):
            g['expenses'].append(exps[ei])
            ei += 1
        groups.append(g)
    return groups


def _build_ledger(ctx, fs, pad):
    is_urdu, shape, f = ctx['is_urdu'], ctx['shape'], ctx['fonts']
    font_bold = f['bold']
    lead = round(fs * 1.25, 2)
    L = lambda ur, en: ur if is_urdu else en

    # column widths - amount columns amount ki lambai se, baaqi mein taqseem
    max_amt = max([abs(ctx['total_income']), abs(ctx['total_expense']), abs(ctx['net_balance'])] +
                  [abs(i['amount']) for i in ctx['income_items']] +
                  [abs(i['amount']) for i in ctx['expense_items']] + [0])
    amt_w = max(52, stringWidth("-" + money(max_amt), font_bold, fs + 0.5) + 8)
    hdr_w = stringWidth("00-Mmm-0000", font_bold, fs) + 9
    date_w = max(54, hdr_w)
    bal_w = amt_w + 6
    rest = CONTENT_W - date_w - amt_w * 2 - bal_w
    src_w = round(rest * 0.36)
    det_w = rest - src_w
    widths = [date_w, src_w, det_w, amt_w, amt_w, bal_w]

    txt = _ps('lg_t', font_bold, fs, INK, 0, lead)
    txt_inc = _ps('lg_ti', font_bold, fs, "#064e3b", 0, lead)
    a_inc = _ps('lg_ai', font_bold, fs, "#15803d", 2, lead)
    a_exp = _ps('lg_ae', font_bold, fs, "#b91c1c", 2, lead)
    a_bal = _ps('lg_ab', font_bold, fs, "#0c4a6e", 2, lead)
    a_bal_neg = _ps('lg_an', font_bold, fs, "#b91c1c", 2, lead)
    hdr = _ps('lg_h', font_bold, fs + 0.5, "#ffffff", 0, round((fs + 0.5) * 1.25, 2))
    hdr_r = _ps('lg_hr', font_bold, fs + 0.5, "#ffffff", 2, round((fs + 0.5) * 1.25, 2))
    title = _ps('lg_title', font_bold, fs + 1.5, GOLD_LIGHT, 1, round((fs + 1.5) * 1.25, 2))
    tot_l = _ps('lg_tl', font_bold, fs + 0.5, "#ffffff", 0, round((fs + 0.5) * 1.25, 2))
    tot_i = _ps('lg_ti2', font_bold, fs + 0.5, GOLD_LIGHT, 2, round((fs + 0.5) * 1.25, 2))
    tot_e = _ps('lg_te', font_bold, fs + 0.5, "#fee2e2", 2, round((fs + 0.5) * 1.25, 2))
    tot_b = _ps('lg_tb', font_bold, fs + 0.5, "#e0f2fe", 2, round((fs + 0.5) * 1.25, 2))

    P = lambda t, s: Paragraph(t, s)
    S = lambda t, s: Paragraph(esc(shape(t, is_urdu)), s)
    fmt_date = lambda d: d.strftime('%d-%b-%Y')

    rows = [
        [Paragraph("<b>%s</b>" % esc(shape(L("آمدنی و اخراجات کا مکمل گوشوارہ (روپے)",
                                                "INCOME & EXPENSE LEDGER (PKR)"), is_urdu)), title),
         "", "", "", "", ""],
        [S(L("تاریخ", "Date"), hdr), S(L("ذریعہ / قسم", "Source / Category"), hdr),
         S(L("تفصیل / نوٹس", "Details / Notes"), hdr), S(L("آمدنی", "Income"), hdr_r),
         S(L("اخراجات", "Expense"), hdr_r), S(L("بقایا", "Balance"), hdr_r)],
    ]
    style = [
        ('FONTSIZE', (0, 0), (-1, -1), 1), ('LEADING', (0, 0), (-1, -1), 1),   # khali cells row ko lamba na karein
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), _c(EMERALD)),
        ('BACKGROUND', (0, 1), (-1, 1), _c(EMERALD_MID)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 1), (-1, -1), 0.4, _c("#94a3b8")),
        ('BOX', (0, 0), (-1, -1), 1.2, _c(EMERALD)),
        ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]

    balance = 0
    groups = group_ledger(ctx['income_items'], ctx['expense_items'])
    n_groups = 0
    for g in groups:
        first_row_of_group = len(rows)
        n_groups += 1
        if g['income'] is not None:
            it = g['income']
            balance += it['amount']
            rows.append([P(fmt_date(it['date']), txt_inc), S(it['source'], txt_inc), S(it['notes'], txt_inc),
                         P(money(it['amount']), a_inc), "", P(money(balance), a_bal_neg if balance < 0 else a_bal)])
            style.append(('BACKGROUND', (0, len(rows) - 1), (-1, len(rows) - 1), _c("#d1fae5")))
        for k, ex in enumerate(g['expenses']):
            balance -= ex['amount']
            rows.append([P(fmt_date(ex['date']), txt), S(ex['category'], txt), S(ex['description'], txt),
                         "", P(money(ex['amount']), a_exp), P(money(balance), a_bal_neg if balance < 0 else a_bal)])
            style.append(('BACKGROUND', (0, len(rows) - 1), (-1, len(rows) - 1),
                          _c("#ffffff") if k % 2 == 0 else _c("#fef2f2")))
        last = len(rows) - 1
        # is group ka "baqi" (income + us ke expenses ke baad) - balance cell highlight
        style.append(('BACKGROUND', (5, last), (5, last), _c("#fef9c3")))
        style.append(('LINEBELOW', (0, last), (-1, last), 1.0, _c(EMERALD)))
        if first_row_of_group > 2:
            style.append(('LINEABOVE', (0, first_row_of_group), (-1, first_row_of_group), 1.0, _c(EMERALD)))

    if not groups:
        rows.append([S(L("اس عرصے میں کوئی آمدنی یا اخراجات درج نہیں۔", "No income or expenses recorded for this period."), txt),
                     "", "", "", "", ""])
        style.append(('SPAN', (0, 2), (-1, 2)))
    else:
        rows.append([P("<b>%s</b>" % esc(shape(L("کل مجموعہ / بقایا بیلنس", "GRAND TOTAL / NET BALANCE"), is_urdu)), tot_l),
                     "", "", P(money(ctx['total_income']), tot_i), P(money(ctx['total_expense']), tot_e),
                     P(money(ctx['net_balance']), tot_b)])
        style += [('SPAN', (0, -1), (2, -1)), ('BACKGROUND', (0, -1), (-1, -1), _c(EMERALD)),
                  ('LINEABOVE', (0, -1), (-1, -1), 1.2, _c(GOLD))]

    tbl = Table(rows, colWidths=widths, repeatRows=2)
    tbl.setStyle(TableStyle(style))
    return tbl


# ==========================================================================
#  Imam salary + land lease (bottom block)
# ==========================================================================
def _build_imam(ctx, fs, pad, width):
    is_urdu, shape, f = ctx['is_urdu'], ctx['shape'], ctx['fonts']
    fb = f['bold']
    lead = round(fs * 1.25, 2)
    L = lambda ur, en: ur if is_urdu else en
    S = lambda t, s: Paragraph(esc(shape(t, is_urdu)), s)

    title = _ps('im_title', fb, fs + 1.5, GOLD_LIGHT, 1, round((fs + 1.5) * 1.25, 2))
    cell = _ps('im_c', fb, fs, INK, 0, lead)
    hdr = _ps('im_h', fb, fs + 0.3, "#ffffff", 0, round((fs + 0.3) * 1.25, 2))
    amt = _ps('im_a', fb, fs, "#1b5e20", 2, lead)
    name_st = _ps('im_n', fb, fs + 0.5, "#ffffff", 0, round((fs + 0.5) * 1.25, 2))
    w1 = round(width * 0.33)
    w3 = round(width * 0.33)
    widths = [w1, width - w1 - w3, w3]

    rows = [[Paragraph("<b>%s</b>" % esc(shape(L("امام کی تنخواہ کا ریکارڈ", "IMAM SALARY RECORD"), is_urdu)), title), "", ""]]
    style = [
        ('FONTSIZE', (0, 0), (-1, -1), 1), ('LEADING', (0, 0), (-1, -1), 1),   # khali cells row ko lamba na karein
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), _c(EMERALD)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 1), (-1, -1), 0.4, _c(EMERALD)), ('BOX', (0, 0), (-1, -1), 1.2, _c(EMERALD)),
        ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    recs = ctx['imams']
    if not recs:
        rows.append([S(L("اس عرصے کے لیے کوئی تنخواہ کا ریکارڈ نہیں۔", "No Imam salary records."), cell), "", ""])
        style += [('SPAN', (0, 1), (-1, 1)), ('BACKGROUND', (0, 1), (-1, 1), _c("#ffffff"))]
    for r in recs:
        i = len(rows)
        st_col = "#a7f3d0" if r['is_paid'] else "#fecaca"
        rows.append([Paragraph("<b>%s</b>" % esc(shape(r['name'], is_urdu)), name_st), "",
                     Paragraph("<b>%s</b>" % esc(shape(L("مکمل ادا", "PAID") if r['is_paid'] else L("بقایا", "PENDING"), is_urdu)),
                               _ps('im_s', fb, fs, st_col, 2, lead))])
        style += [('SPAN', (0, i), (1, i)), ('BACKGROUND', (0, i), (-1, i), _c(EMERALD_MID))]
        rows.append([S(L("تاریخ", "Date"), hdr), S(L("اقساط / تفصیل", "Installment / Details"), hdr),
                     Paragraph(esc(shape(L("ادائیگی", "Paid (PKR)"), is_urdu)), _ps('im_hr', fb, fs + 0.3, "#ffffff", 2))])
        style.append(('BACKGROUND', (0, i + 1), (-1, i + 1), _c("#1f2937")))
        if r['installments']:
            for k, ins in enumerate(r['installments']):
                j = len(rows)
                rows.append([Paragraph(ins['date'].strftime('%d-%b-%Y'), cell),
                             S(ins['note'] or L("قسط کی ادائیگی", "Installment"), cell),
                             Paragraph(money(ins['amount']), amt)])
                style.append(('BACKGROUND', (0, j), (-1, j), _c("#ffffff") if k % 2 == 0 else _c("#f1f5f9")))
        else:
            j = len(rows)
            rows.append([S(L("کوئی قسط کی ادائیگی نہیں ہوئی", "No installments"), cell), "", ""])
            style += [('SPAN', (0, j), (-1, j)), ('BACKGROUND', (0, j), (-1, j), _c("#ffffff"))]
        bar = lambda col, al=0: _ps('im_bar', fb, fs + 0.3, col, al, round((fs + 0.3) * 1.25, 2))
        rem_m = "#a7f3d0" if r['month_remaining'] <= 0 else GOLD_LIGHT
        rem_y = "#a7f3d0" if r['yearly_remaining'] <= 0 else GOLD_LIGHT
        j = len(rows)
        rows.append([
            Paragraph("<b>%s: RS %s</b>" % (esc(shape(L("ماھانہ کل تنخواہ", "Monthly Salary"), is_urdu)), money(r['monthly_total'])), bar("#ffffff")),
            Paragraph("<b>%s: RS %s</b>" % (esc(shape(L("ماھانہ ادا شدہ", "Total Paid"), is_urdu)), money(r['total_paid'])), bar("#a7f3d0")),
            Paragraph("<b>%s: RS %s</b>" % (esc(shape(L("ماهانہ بقایا", "Month Remaining"), is_urdu)), money(r['month_remaining'])), bar(rem_m, 2)),
        ])
        rows.append([
            Paragraph("<b>%s: RS %s</b>" % (esc(shape(L("سالانہ کل تنخواہ", "Yearly Salary"), is_urdu)), money(r['yearly_total'])), bar("#ffffff")),
            "",
            Paragraph("<b>%s: RS %s</b>" % (esc(shape(L("سالانہ بقایا", "Year Remaining"), is_urdu)), money(r['yearly_remaining'])), bar(rem_y, 2)),
        ])
        style += [('BACKGROUND', (0, j), (-1, j), _c(EMERALD)), ('BACKGROUND', (0, j + 1), (-1, j + 1), _c(INK)),
                  ('SPAN', (0, j + 1), (1, j + 1))]
    tbl = Table(rows, colWidths=widths)
    tbl.setStyle(TableStyle(style))
    return tbl


def _build_lease_card(ctx, fs, width):
    """Side ka lease card (original design) - font bottom_fs ke saath chhota/bara hota hai."""
    is_urdu, shape, fb = ctx['is_urdu'], ctx['shape'], ctx['fonts']['bold']
    fs = max(fs, 4.6)
    lead = round(fs * 1.2, 2)
    L = lambda ur, en: ur if is_urdu else en
    S = lambda t, st: Paragraph(esc(shape(t, is_urdu)), st)
    lbl = _ps('ls_l', fb, fs, "#065f46", 0, lead)
    val = _ps('ls_v', fb, fs, INK, 0, lead)
    hdr = _ps('ls_h', fb, fs + 0.6, "#ffffff", 1, round((fs + 0.6) * 1.2, 2))
    sub = _ps('ls_s', fb, fs, "#fde047", 1, lead)
    first = ctx['leases'][0]
    head = ("<b>%s</b><br/><font size='%.1f' color='#fef08a'><b>%s RS %s | %s RS %s</b></font>" % (
        esc(shape(L("زمین کا ٹھیکہ", "Zameen Ka Theka"), is_urdu)), fs,
        esc(shape(L("طے:", "Agreed:"), is_urdu)), money(first['total']),
        esc(shape(L("بقایا:", "Rem:"), is_urdu)), money(first['remaining'])))
    rows = [[Paragraph(head, hdr), ""]]
    blocks = []
    for l in ctx['leases']:
        status = L("مکمل ادا", "PAID") if l['is_paid'] else L("فعال ٹھیکہ", "ACTIVE")
        rem_col = "#15803d" if l['remaining'] <= 0 else "#dc2626"
        data = [
            (L("ٹھیکیدار:", "Tenant:"), "<b>%s</b>" % esc(shape(l['tenant'], is_urdu))),
            (L("رابطہ:", "Phone:"), "<font color='#1e40af'><b>%s</b></font>" % esc(l['phone'] or "-")),
            (L("رقبہ:", "Area:"), "<font color='#047857'><b>%s</b></font>" % esc(shape(l['area'], is_urdu))),
            (L("مدت:", "Period:"), "<font color='#334155'>%s</font>" % esc(l['duration'])),
            (L("کل رقم:", "Agreed:"), "<b>RS %s</b>" % money(l['total'])),
            (L("وصول شدہ:", "Received:"), "<font color='#15803d'><b>RS %s</b></font>" % money(l['received'])),
            (L("بقایا رقم:", "Remaining:"), "<font color='%s'><b>RS %s</b></font> (%s)" % (rem_col, money(l['remaining']), esc(shape(status, is_urdu)))),
        ]
        for k, v in data:
            rows.append([S(k, lbl), Paragraph(v, val)])
        sub_i = len(rows)
        rows.append([S(L("اقساط کا ریکارڈ", "INSTALLMENTS RECORD"), sub), ""])
        start = len(rows)
        if l['payments']:
            for p in l['payments']:
                note = esc(shape(p['note'], is_urdu)) if p['note'] else L("ٹھیکہ وصولی", "Lease Payment")
                rows.append([Paragraph("<font color='#047857'><b>%s</b></font>" % p['date'].strftime('%d-%b-%Y'), val),
                             Paragraph("<font color='#15803d'><b>+RS %s</b></font><br/><font color='#475569'>%s</font>" % (money(p['amount']), note), val)])
        else:
            rows.append([S(L("کوئی قسط موصول نہیں ہوئی", "No payments received"), val), ""])
        blocks.append((sub_i, start, len(rows) - 1))
    lw = round((width - 6) * 0.34)
    tbl = Table(rows, colWidths=[lw, width - 6 - lw])
    style = [
        ('FONTSIZE', (0, 0), (-1, -1), 1), ('LEADING', (0, 0), (-1, -1), 1),
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), _c(EMERALD_DARK)),
        ('LINEBELOW', (0, 0), (-1, 0), 1.0, _c(GOLD)), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0.6), ('BOTTOMPADDING', (0, 0), (-1, -1), 0.6),
        ('LEFTPADDING', (0, 0), (-1, -1), 1.5), ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
    ]
    for r_i in range(1, len(rows)):
        style.append(('BACKGROUND', (0, r_i), (-1, r_i), _c("#f8fafc") if r_i % 2 else _c("#ffffff")))
    for sub_i, start, end in blocks:
        style += [('BACKGROUND', (0, sub_i), (-1, sub_i), _c(EMERALD)),
                  ('BACKGROUND', (0, start), (-1, end), _c("#f0fdf4")),
                  ('GRID', (0, start), (-1, end), 0.3, _c("#a7f3d0"))]
    for idx, row in enumerate(rows):
        if len(row) > 1 and row[1] == "":
            style.append(('SPAN', (0, idx), (-1, idx)))
    tbl.setStyle(TableStyle(style))
    return _Card(tbl, width)


def _build_bottom(ctx, fs, pad):
    """Imam salary (left) + lease card (right) ek hi line mein; lease na ho to imam poori chorai."""
    if ctx['leases']:
        gap, card_w = 10, 160
        imam = _build_imam(ctx, fs, pad, CONTENT_W - gap - card_w)
        card = _build_lease_card(ctx, fs, card_w)
        row = Table([[imam, "", card]], colWidths=[CONTENT_W - gap - card_w, gap, card_w])
        row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                 ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 0)]))
        return [row]
    is_urdu, shape, fb = ctx['is_urdu'], ctx['shape'], ctx['fonts']['bold']
    msg = ("زمین کا ٹھیکہ: اس عرصے کے لیے کوئی فعال ٹھیکہ نہیں" if is_urdu
           else "Zameen Ka Theka: No active leases for this period")
    strip = Table([[Paragraph("<b>%s</b>" % esc(shape(msg, is_urdu)), _ps('ls_none', fb, fs, "#334155", 1))]],
                  colWidths=[CONTENT_W])
    strip.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), _c("#f8fafc")),
                               ('BOX', (0, 0), (-1, -1), 0.8, _c("#047857")),
                               ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad)]))
    return [_build_imam(ctx, fs, pad, CONTENT_W), Spacer(1, 3), strip]


def _height(flowables):
    total = 0
    for fl in flowables:
        _, h = fl.wrap(CONTENT_W, 10 ** 7)
        total += h + getattr(fl, 'spaceBefore', 0) + getattr(fl, 'spaceAfter', 0)
    return total


# ==========================================================================
#  Public entry
# ==========================================================================
def render_monthly_pdf(ctx, background_cb):
    """Returns (pdf_bytes, info). info = {'font_size', 'single_page', 'pages'} (debug / tests)."""
    import io
    levels = LEVELS_URDU if ctx['is_urdu'] else LEVELS_EN

    # --- Stage 1: ledger ka sab se bara font jo is tarah aaye ke neeche ke sections minimum
    #     size (BOTTOM_MIN) par hon.   Stage 2: us font par neeche ke sections jitne bare ho sakein.
    def ledger_part(i):
        fs, pad, compact = levels[i]
        return _build_header(ctx, compact), [_build_ledger(ctx, fs, pad), Spacer(1, 4)]

    def bottom_part(i, bfs):
        pad = max(0.5, min(levels[i][1], 1.6))
        return _build_bottom(ctx, bfs, pad)

    def fits_at(i, bfs):
        h, led = ledger_part(i)
        return _height(h) + _height(led) + _height(bottom_part(i, bfs)) <= FRAME_H - FIT_SAFETY

    def search(floor_of):
        lo, hi, found = 0, len(levels) - 1, None
        while lo <= hi:                               # binary search (bara -> chhota font)
            mid = (lo + hi) // 2
            if fits_at(mid, floor_of(levels[mid][0])):
                found, hi = mid, mid - 1
            else:
                lo = mid + 1
        return found

    # Pehle: neeche ke sections ledger ke ~80% font par (balanced look). Agar phir bhi na aaye
    # to neeche ke sections minimum tak chhote hote jate hain, phir ledger chhota hota hai.
    ratio_floor = lambda f: max(BOTTOM_MIN, min(BOTTOM_MAX, round(f * 0.8, 2)))
    found = search(ratio_floor)
    floor_of = ratio_floor
    if found is None:
        found = search(lambda f: BOTTOM_MIN)
        floor_of = lambda f: BOTTOM_MIN
    fits = found is not None
    idx = found if fits else len(levels) - 1
    bfs = floor_of(levels[idx][0])
    if fits:                                          # ab neeche ke sections jitne bare ho sakein
        v = min(levels[idx][0], BOTTOM_MAX)
        while v > bfs + 1e-9:
            if fits_at(idx, round(v, 2)):
                bfs = round(v, 2)
                break
            v -= 0.2
    header, led = ledger_part(idx)
    story = header + led + bottom_part(idx, bfs)
    chosen = levels[idx]
    if not fits:
        # aakhri hal: poora page proportionally shrink - data kabhi doosre page par nahi jata
        story = [KeepInFrame(CONTENT_W, FRAME_H - FIT_SAFETY, story, mode='shrink')]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, pageCompression=1,
                          leftMargin=(PAGE_W - CONTENT_W) / 2, rightMargin=(PAGE_W - CONTENT_W) / 2,
                          topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
                          title="Masjid Financial Statement", author="Jameya Masjid")
    frame = Frame((PAGE_W - CONTENT_W) / 2, MARGIN_BOTTOM, CONTENT_W, FRAME_H, id='main',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='a4', frames=[frame], onPage=background_cb, pagesize=A4)])
    doc.build(story)
    return buf.getvalue(), {'font_size': chosen[0], 'padding': chosen[1], 'compact_header': chosen[2],
                            'bottom_font': bfs, 'fully_fit': fits, 'pages': doc.page}