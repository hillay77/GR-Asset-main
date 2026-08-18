import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PRIMARY = colors.HexColor('#1F5AA6')
HEADER_BG = colors.HexColor('#EAF2FF')
HEADER_TEXT = colors.black


def scaled_col_widths(weights, page_width):
    """Return proportional column widths from a list of weights."""
    if not weights:
        return []
    total = sum(weights)
    if total <= 0:
        return [page_width / len(weights) for _ in weights]
    return [max(24, (w / total) * page_width) for w in weights]


def asset_register_col_widths(page_width):
    """Column widths for the asset register PDF table."""
    return scaled_col_widths([55, 60, 115, 60, 90, 65, 55, 48, 80, 55, 70], page_width)


def return_log_col_widths(page_width):
    """Column widths for return log PDF table."""
    return scaled_col_widths([50, 100, 70, 55, 55, 120], page_width)


def build_pdf_table(rows, col_widths):
    """Create a styled ReportLab table with a header row."""
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
                ('TEXTCOLOR', (0, 0), (-1, 0), HEADER_TEXT),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_gr_pdf(body, report_title='GR Asset Register'):
    """Generate a PDF document from a body-building callback."""
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    title = Paragraph(report_title, styles['Title'])
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = [title, Spacer(1, 12)]
    if callable(body):
        story.extend(body(doc))
    else:
        story.extend(body)
    doc.build(story)
    return buffer.getvalue()


def pdf_response(pdf_bytes, filename):
    """Return an attachment response containing PDF bytes."""
    from flask import make_response

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
