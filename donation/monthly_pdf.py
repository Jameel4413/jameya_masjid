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
    BaseDocTemplate, Frame, Image as RLImage, KeepTogether, PageTemplate, Spacer, Table, TableStyle,
)

from .urdu_pdf import Paragraph

PAGE_W, PAGE_H = A4
CONTENT_W = 535                      # A4 width (595.3) minus ~30pt margin each side
MARGIN_TOP = 30
MARGIN_BOTTOM = 42                   # footer line / page number background ke liye jagah
FRAME_H = PAGE_H - MARGIN_TOP - MARGIN_BOTTOM
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


# ==========================================================================
#  Header (fixed size)
# ==========================================================================
def _build_header(ctx, compact=False):
    f, shape = ctx['fonts'], ctx['shape']
    is_urdu = ctx['is_urdu']
    font_bism, font_bold = f['bism'], f['bold']
    ur_font = f.get('urdu') or font_bism
    story = []
    img_h = 48 if compact else 66

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
        if path and os.path.exists(path):
            try:
                from reportlab.lib.utils import ImageReader
                iw, ih = ImageReader(path).getSize()
                return RLImage(path, width=h * iw / ih, height=h)
            except Exception:
                pass
        return ""

    box = Table([[_img(ctx.get('gumbad_path'), img_h), center, _img(ctx.get('kaaba_path'), img_h)]],
                colWidths=[side_w, center_w, side_w])
    box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), _c(EMERALD_DARK)),
        ('BOX', (0, 0), (-1, -1), 2.2, _c(GOLD)),
        ('LINEABOVE', (0, 0), (-1, -1), 1.0, _c(GOLD_LIGHT)),
        ('LINEBELOW', (0, 0), (-1, -1), 1.0, _c(GOLD_LIGHT)),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'), ('ALIGN', (1, 0), (1, 0), 'CENTER'), ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (0, 0), 4), ('RIGHTPADDING', (2, 0), (2, 0), 4),
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


def _build_lease_table(ctx, fs, pad):
    """Zameen ke theke ki full-width compact table (sirf tab jab lease maujood ho)."""
    is_urdu, shape, fb = ctx['is_urdu'], ctx['shape'], ctx['fonts']['bold']
    lead = round(fs * 1.25, 2)
    L = lambda ur, en: ur if is_urdu else en
    S = lambda t, s_: Paragraph(esc(shape(t, is_urdu)), s_)
    lbl = _ps('ls_l', fb, fs, "#065f46", 0, lead)
    val = _ps('ls_v', fb, fs, INK, 0, lead)
    hdr = _ps('ls_h', fb, fs + 1.5, GOLD_LIGHT, 1, round((fs + 1.5) * 1.25, 2))
    sub = _ps('ls_s', fb, fs + 0.3, "#fde047", 1, lead)
    first = ctx['leases'][0]
    head = "<b>%s</b>" % esc(shape(L("زمین کا ٹھیکہ", "Zameen Ka Theka"), is_urdu))
    if len(ctx['leases']) == 1:
        head += "  <font color='#ffffff'>|  %s RS %s  |  %s RS %s</font>" % (
            esc(shape(L("طے:", "Agreed:"), is_urdu)), money(first['total']),
            esc(shape(L("بقایا:", "Remaining:"), is_urdu)), money(first['remaining']))
    lw, vw = 56, 122
    widths = [lw, vw, lw, vw, lw, CONTENT_W - 2 * (lw + vw) - lw]
    rows = [[Paragraph(head, hdr), "", "", "", "", ""]]
    style = [
        ('FONTSIZE', (0, 0), (-1, -1), 1), ('LEADING', (0, 0), (-1, -1), 1),   # khali cells row ko lamba na karein
        ('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 0), _c(EMERALD_DARK)),
        ('BOX', (0, 0), (-1, -1), 1.2, _c("#047857")), ('GRID', (0, 1), (-1, -1), 0.3, _c("#a7f3d0")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 3), ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]
    for l in ctx['leases']:
        status = L("مکمل ادا", "PAID") if l['is_paid'] else L("فعال ٹھیکہ", "ACTIVE")
        rem_col = "#15803d" if l['remaining'] <= 0 else "#dc2626"
        i = len(rows)
        pair = lambda k, v: [S(k, lbl), Paragraph(v, val)]
        rows.append(pair(L("ٹھیکیدار:", "Tenant:"), "<b>%s</b>" % esc(shape(l['tenant'], is_urdu))) +
                    pair(L("رابطہ:", "Phone:"), "<font color='#1e40af'><b>%s</b></font>" % esc(l['phone'] or "-")) +
                    pair(L("رقبہ:", "Area:"), "<font color='#047857'><b>%s</b></font>" % esc(shape(l['area'], is_urdu))))
        rows.append(pair(L("مدت:", "Period:"), "<font color='#334155'>%s</font>" % esc(l['duration'])) +
                    pair(L("کل رقم:", "Agreed:"), "<b>RS %s</b>" % money(l['total'])) +
                    pair(L("وصول شدہ:", "Received:"), "<font color='#15803d'><b>RS %s</b></font>" % money(l['received'])))
        rows.append([S(L("بقایا رقم:", "Remaining:"), lbl),
                     Paragraph("<font color='%s'><b>RS %s</b></font> (%s)" % (rem_col, money(l['remaining']), esc(shape(status, is_urdu))), val),
                     "", "", "", ""])
        style += [('SPAN', (1, i + 2), (-1, i + 2)),
                  ('BACKGROUND', (0, i), (-1, i), _c("#f8fafc")), ('BACKGROUND', (0, i + 1), (-1, i + 1), _c("#ffffff")),
                  ('BACKGROUND', (0, i + 2), (-1, i + 2), _c("#f8fafc"))]
        sub_i = len(rows)
        rows.append([S(L("اقساط کا ریکارڈ", "INSTALLMENTS RECORD"), sub), "", "", "", "", ""])
        style += [('SPAN', (0, sub_i), (-1, sub_i)), ('BACKGROUND', (0, sub_i), (-1, sub_i), _c(EMERALD))]
        if l['payments']:
            for p in l['payments']:
                j = len(rows)
                note = esc(shape(p['note'], is_urdu)) if p['note'] else L("ٹھیکہ وصولی", "Lease Payment")
                rows.append([Paragraph("<font color='#047857'><b>%s</b></font>" % p['date'].strftime('%d-%b-%Y'), val), "",
                             Paragraph("<font color='#15803d'><b>+RS %s</b></font>" % money(p['amount']), val), "",
                             Paragraph("<font color='#475569'>%s</font>" % note, val), ""])
                style += [('SPAN', (0, j), (1, j)), ('SPAN', (2, j), (3, j)), ('SPAN', (4, j), (5, j)),
                          ('BACKGROUND', (0, j), (-1, j), _c("#f0fdf4"))]
        else:
            j = len(rows)
            rows.append([S(L("کوئی قسط موصول نہیں ہوئی", "No payments received"), val), "", "", "", "", ""])
            style += [('SPAN', (0, j), (-1, j)), ('BACKGROUND', (0, j), (-1, j), _c("#f0fdf4"))]
    tbl = Table(rows, colWidths=widths)
    tbl.setStyle(TableStyle(style))
    return tbl


def _build_bottom(ctx, fs, pad):
    out = [_build_imam(ctx, fs, pad, CONTENT_W)]
    if ctx['leases']:
        out += [Spacer(1, 3), _build_lease_table(ctx, fs, pad)]
    else:
        # lease nahi hai to khali card ke bajaye ek patli patti
        is_urdu, shape, fb = ctx['is_urdu'], ctx['shape'], ctx['fonts']['bold']
        msg = ("زمین کا ٹھیکہ: اس عرصے کے لیے کوئی فعال ٹھیکہ نہیں" if is_urdu
               else "Zameen Ka Theka: No active leases for this period")
        strip = Table([[Paragraph("<b>%s</b>" % esc(shape(msg, is_urdu)), _ps('ls_none', fb, fs, "#334155", 1))]],
                      colWidths=[CONTENT_W])
        strip.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), _c("#f8fafc")),
                                   ('BOX', (0, 0), (-1, -1), 0.8, _c("#047857")),
                                   ('TOPPADDING', (0, 0), (-1, -1), pad), ('BOTTOMPADDING', (0, 0), (-1, -1), pad)]))
        out += [Spacer(1, 3), strip]
    return out


def _build_body(ctx, fs, pad):
    return [_build_ledger(ctx, fs, pad), Spacer(1, 4)], _build_bottom(ctx, fs, pad)


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

    def attempt(i):
        fs, pad, compact = levels[i]
        header, body = _build_header(ctx, compact), None
        body = _build_body(ctx, fs, pad)
        ok = _height(header) + _height(body[0]) + _height(body[1]) <= FRAME_H - FIT_SAFETY
        return header, body, ok

    lo, hi = 0, len(levels) - 1          # sab se bara font jo ek page mein aaye (binary search)
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        h, bd, ok = attempt(mid)
        if ok:
            best, hi = (mid, h, bd), mid - 1
        else:
            lo = mid + 1
    fits = best is not None
    if not fits:                          # minimum size par bhi na aaye -> agla A4 page
        h, bd, _ = attempt(len(levels) - 1)
        best = (len(levels) - 1, h, bd)
    idx, header, body = best
    chosen = levels[idx]

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, pageCompression=1,
                          leftMargin=(PAGE_W - CONTENT_W) / 2, rightMargin=(PAGE_W - CONTENT_W) / 2,
                          topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
                          title="Masjid Financial Statement", author="Jameya Masjid")
    frame = Frame((PAGE_W - CONTENT_W) / 2, MARGIN_BOTTOM, CONTENT_W, FRAME_H, id='main',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='a4', frames=[frame], onPage=background_cb, pagesize=A4)])
    # neeche ka imam/lease block ek saath rahe (do page mein na tute)
    doc.build(header + body[0] + [KeepTogether(body[1])])
    return buf.getvalue(), {'font_size': chosen[0], 'padding': chosen[1], 'compact_header': chosen[2],
                            'single_page': fits, 'pages': doc.page}