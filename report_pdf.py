"""Builds the downloadable patient assessment PDF (ReportLab)."""
import io
import base64
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, KeepTogether, ListFlowable, ListItem)

APP_NAME = "Medicine Recommendation System"
DARK = colors.HexColor('#1D2D50')
PRIMARY = colors.HexColor('#3A7BD5')
ACCENT = colors.HexColor('#8EC5FF')
SOFT = colors.HexColor('#D6ECFF')
BG = colors.HexColor('#F6FBFF')
MUTED = colors.HexColor('#5B6B8C')
DANGER = colors.HexColor('#D93B3B')

S = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=16, textColor=colors.white, leading=20),
    'sub': ParagraphStyle('sub', fontName='Helvetica', fontSize=9, textColor=SOFT, leading=12),
    'h2': ParagraphStyle('h2', fontName='Helvetica-Bold', fontSize=11.5, textColor=DARK, leading=14,
                         spaceBefore=8, spaceAfter=3),
    'label': ParagraphStyle('label', fontName='Helvetica-Bold', fontSize=7.5, textColor=MUTED, leading=10),
    'value': ParagraphStyle('value', fontName='Helvetica', fontSize=9.5, textColor=DARK, leading=12.5),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.5, textColor=DARK, leading=13),
    'disease': ParagraphStyle('disease', fontName='Helvetica-Bold', fontSize=15, textColor=colors.white, leading=19),
    'small_w': ParagraphStyle('small_w', fontName='Helvetica', fontSize=8.5, textColor=SOFT, leading=11),
    'name': ParagraphStyle('name', fontName='Helvetica-Bold', fontSize=14, textColor=DARK, leading=17),
    'note': ParagraphStyle('note', fontName='Helvetica-Oblique', fontSize=8, textColor=MUTED, leading=11),
}


def _p(text, style='value'):
    text = escape(str(text or '-')).replace('\n', '<br/>')
    return Paragraph(text, S[style])


def _photo(data_uri, size=28 * mm):
    if not data_uri or ';base64,' not in data_uri:
        return None
    try:
        raw = base64.b64decode(data_uri.split(';base64,', 1)[1])
        reader = ImageReader(io.BytesIO(raw))
        w, h = reader.getSize()
        scale = size / max(w, h)
        return Image(io.BytesIO(raw), width=w * scale, height=h * scale)
    except Exception:
        return None  # unsupported image (e.g. some WEBP builds) -> report without photo


def _bullets(items):
    return ListFlowable(
        [ListItem(_p(i, 'body'), leftIndent=10, value='circle') for i in items],
        bulletType='bullet', bulletColor=PRIMARY, bulletFontSize=6, leftIndent=12, spaceBefore=0)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(SOFT)
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9.5 * mm, f"{APP_NAME}  |  Automated suggestion only - not a medical diagnosis.")
    canvas.drawRightString(A4[0] - 18 * mm, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf_report(ctx):
    p = ctx.get('patient', {})
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=18 * mm,
                            title=f"Patient Report - {p.get('name', '')}", author=APP_NAME)
    width = A4[0] - 36 * mm
    story = []

    # Header band
    now = datetime.now().strftime('%d %b %Y, %I:%M %p')
    header = Table([[
        [_p(APP_NAME, 'title'), Spacer(1, 2), _p('Patient Assessment Report', 'sub')],
        Paragraph(f"Generated<br/>{escape(now)}", ParagraphStyle('subr', parent=S['sub'], alignment=2)),
    ]], colWidths=[width * 0.68, width * 0.32])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story += [header, Spacer(1, 4)]

    # Patient details
    story.append(Paragraph('Patient details', S['h2']))
    weight = f"{p['weight']} kg" if p.get('weight') else '-'
    height = f"{p['height']} cm" if p.get('height') else '-'
    contact = p.get('phone', '-') + (f"\n{p['email']}" if p.get('email') else '')

    def cell(label, value, style='value'):
        return [_p(label.upper(), 'label'), Spacer(1, 1), _p(value, style)]

    grid = Table([
        [cell('Age', f"{p.get('age', '-')} years"), cell('Gender', p.get('gender') or '-'),
         cell('Blood group', p.get('blood_group') or '-')],
        [cell('Contact', contact), cell('Weight', weight), cell('Height', height)],
    ], colWidths=[None] * 3)
    grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                              ('LEFTPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))

    photo = _photo(p.get('photo'))
    left = [_p(p.get('name', '-'), 'name'), Spacer(1, 8), grid]
    top = Table([[left, photo or '']], colWidths=[width - 34 * mm, 34 * mm])
    top.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BG), ('BOX', (0, 0), (-1, -1), 0.8, SOFT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(top)

    # Medical background
    story.append(Paragraph('Medical background', S['h2']))
    allergy = p.get('allergies') or '-'
    allergy_style = ParagraphStyle('allergy', parent=S['value'], textColor=DANGER, fontName='Helvetica-Bold') \
        if allergy.lower() not in ['-', 'none', 'no', 'nil', 'na', 'n/a'] else S['value']
    bg = Table([
        [_p('CURRENTLY TAKING MEDICATIONS', 'label'), _p(p.get('current_medications') or '-')],
        [_p('ALLERGIES', 'label'), Paragraph(escape(allergy), allergy_style)],
        [_p('MEDICAL HISTORY', 'label'), _p(p.get('history') or '-')],
        [_p('REPORTED SYMPTOMS', 'label'), _p(ctx.get('user_input') or '-')],
    ], colWidths=[48 * mm, width - 48 * mm])
    bg.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -2), 0.5, SOFT),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(bg)

    # Result banner
    story.append(Spacer(1, 10))
    matched = ', '.join(ctx.get('matched_symptoms') or [])
    banner_rows = [[_p('POSSIBLE CONDITION', 'small_w')], [_p(ctx.get('predicted_disease'), 'disease')]]
    if matched:
        banner_rows.append([_p(f"Recognised symptoms: {matched}", 'small_w')])
    banner = Table(banner_rows, colWidths=[width])
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY),
        ('LEFTPADDING', (0, 0), (-1, -1), 12), ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 10), ('TOPPADDING', (0, 1), (-1, -1), 2),
    ]))
    story.append(banner)

    # Recommendation sections
    story.append(KeepTogether([Paragraph('Description', S['h2']), _p(ctx.get('disease_description'), 'body')]))
    # Precautions / Medications / Workouts / Diet in a 2 x 2 grid of boxes
    def box(title, key):
        return [Paragraph(title, ParagraphStyle('bh', parent=S['h2'], spaceBefore=0)), _bullets(ctx.get(key) or ['-'])]
    half = (width - 8) / 2
    grid2 = Table([
        [box('Precautions', 'disease_precautions'), '', box('Medications', 'disease_medications')],
        [box('Workouts', 'disease_workout'), '', box('Diet', 'disease_diet')],
    ], colWidths=[half, 8, half])
    grid2.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (0, 0), 0.8, SOFT), ('BOX', (2, 0), (2, 0), 0.8, SOFT),
        ('BOX', (0, 1), (0, 1), 0.8, SOFT), ('BOX', (2, 1), (2, 1), 0.8, SOFT),
        ('BACKGROUND', (0, 0), (0, -1), BG), ('BACKGROUND', (2, 0), (2, -1), BG),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (1, 0), (1, -1), 0), ('RIGHTPADDING', (1, 0), (1, -1), 0),
    ]))
    # vertical gap between the two rows
    grid2.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 6, colors.white)]))
    story.append(Spacer(1, 8))
    story.append(grid2)

    story.append(Spacer(1, 10))
    story.append(_p("Disclaimer: This report is generated automatically from the symptoms entered and is intended "
                    "for general information only. It is not a medical diagnosis or prescription. Always consult a "
                    "qualified doctor before taking any medication, especially if the patient has allergies or is "
                    "already taking other medicines. In an emergency, call your local emergency number immediately.",
                    'note'))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
