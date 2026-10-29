import html
import json
from pathlib import Path
import re
import textwrap

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
BLUE = colors.HexColor("#123653")
TEAL = colors.HexColor("#007F86")


def architecture():
    drawing = Drawing(475, 180)
    def box(x, y, width, title, subtitle, fill):
        drawing.add(Rect(x, y, width, 44, rx=6, fillColor=fill, strokeColor=fill))
        drawing.add(String(x + width / 2, y + 27, title, textAnchor="middle", fontName="Helvetica-Bold", fontSize=10, fillColor=colors.white))
        drawing.add(String(x + width / 2, y + 12, subtitle, textAnchor="middle", fontName="Helvetica", fontSize=8, fillColor=colors.white))
    def arrow(x1, y1, x2, y2):
        drawing.add(Line(x1, y1, x2, y2, strokeColor=TEAL, strokeWidth=1))
        drawing.add(Polygon([x2, y2, x2 - 3, y2 + 6, x2 + 3, y2 + 6], fillColor=TEAL, strokeColor=TEAL))
    for x, name, desc in [(0, "Produit", "catalogue / stocks"), (166, "Commandes", "commandes / copie Produit"), (332, "SAV", "tickets / copie Commande")]:
        box(x, 131, 143, name, desc, BLUE)
        arrow(x + 71, 131, 237, 89)
    box(77, 45, 320, "Redis : Hashes + Lists", "Evenements, idempotence, reprise et outbox persistante", TEAL)
    arrow(237, 45, 237, 16)
    drawing.add(String(250, 29, "Projecteurs Java FIFO / replaceOne", fontSize=8, fillColor=BLUE))
    box(77, -28, 320, "MongoDB : documents et repliques", "products / orders / sav_tickets / copies locales", BLUE)

    drawing.translate(0, 28)
    drawing.height = 208
    return drawing


def main():
    result = json.loads((ROOT / "docs/validation/result.json").read_text(encoding="utf-8"))
    if result["exit_code"] != 0:
        raise RuntimeError("La derniere validation a echoue : ne pas publier un rapport de succes")
    log = (ROOT / "docs/validation/integration.log").read_text(encoding="utf-8")
    match = re.search(r"Ran (\d+) tests", log)
    if not match or "\nOK\n" not in log or "suite Redis/MongoDB" not in log:
        raise RuntimeError("Preuves de validation completes absentes")
    base = "Helvetica"
    bold = "Helvetica-Bold"

    candidates = [(Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")),
                  (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))]
    for regular, heavy in candidates:
        if regular.exists() and heavy.exists():
            pdfmetrics.registerFont(TTFont("Body", str(regular)))
            pdfmetrics.registerFont(TTFont("BodyBold", str(heavy)))
            base, bold = "Body", "BodyBold"
            break
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyReport", fontName=base, fontSize=9.5, leading=14.1, spaceAfter=8, textColor=BLUE))
    styles.add(ParagraphStyle(name="HeadingReport", fontName=bold, fontSize=21, leading=27, spaceAfter=17, textColor=BLUE))
    styles.add(ParagraphStyle(name="SubtitleReport", fontName=bold, fontSize=13, leading=18, spaceAfter=16, textColor=TEAL))
    styles.add(ParagraphStyle(name="CellReport", fontName=base, fontSize=8, leading=11, textColor=BLUE))
    styles.add(ParagraphStyle(name="CodeReport", fontName="Courier", fontSize=8, leading=10.5, backColor=colors.HexColor("#F0F5F8"), borderPadding=8, spaceBefore=5, spaceAfter=13))
    story = []
    source_path = ROOT / "rapport/ProtecPhone-Rapport-NoSQL.txt"
    if not source_path.exists():
        source_path = ROOT / "rapport/ProtecPhone-Rapport-NoSQL.md"
    source = source_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line == "<!-- pagebreak -->":
            story.append(PageBreak())
        elif line == "<!-- architecture -->":
            story.extend([architecture(), Spacer(1, 12)])
        elif line == "<!-- validation -->":
            text = f"Validation réelle : {match.group(1)} tests d'intégration réussis, puis tous les scénarios de panne et de reprise terminés avec le code 0. Fin de l'exécution : {result['finished_utc']}."
            story.append(Paragraph(html.escape(text), styles["BodyReport"]))
        elif line.startswith("# "):
            if not story:
                story.append(Spacer(1, 65))
            story.append(Paragraph(html.escape(line[2:]), styles["HeadingReport"]))
        elif line.startswith("## "):
            story.append(Paragraph(html.escape(line[3:]), styles["SubtitleReport"]))
        elif line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.extend(textwrap.wrap(lines[i], width=94, replace_whitespace=False, drop_whitespace=False) or [""])
                i += 1
            story.append(Preformatted("\n".join(block), styles["CodeReport"]))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", c) for c in cells):
                    rows.append([Paragraph(html.escape(c), styles["CellReport"]) for c in cells])
                i += 1
            i -= 1
            widths = [110, 145, 220] if len(rows[0]) == 3 else [180, 295]
            table = Table(rows, colWidths=widths, hAlign="LEFT")
            table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDECEF")),
                                       ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6F8")]),
                                       ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                       ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 7),
                                       ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
            story.extend([table, Spacer(1, 12)])
        else:
            paragraph = [line]
            while i + 1 < len(lines) and lines[i + 1].strip() and not lines[i + 1].startswith(("#", "|", "```", "<!--")):
                i += 1
                paragraph.append(lines[i].strip())
            story.append(Paragraph(html.escape(" ".join(paragraph)), styles["BodyReport"]))
        i += 1
    target = ROOT / "rapport/ProtecPhone-Rapport-NoSQL.pdf"
    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=60, leftMargin=60, topMargin=52, bottomMargin=48,
                            title="ProtecPhone — Rapport NoSQL", author="Groupe ProtecPhone — EFREI Paris", subject="Redis, MongoDB et architecture microservices")
    def footer(canvas, document):
        canvas.setStrokeColor(TEAL)
        canvas.line(60, 37, A4[0] - 60, 37)
        canvas.setFont(base, 8)
        canvas.setFillColor(BLUE)
        canvas.drawString(60, 24, "ProtecPhone | EFREI Paris | M1")
        canvas.drawRightString(A4[0] - 60, 24, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(target)


if __name__ == "__main__":
    main()
