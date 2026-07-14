"""
Your Gazette — PDF Newspaper Generator
---------------------------------------
Generates a formatted broadsheet-style PDF newspaper from columnist submissions.

Usage:
    python generate_gazette.py

The GAZETTE_DATA dict at the top simulates what will eventually come from a database.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph,
    Spacer, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.platypus.flowables import Flowable
import datetime
import os

# ─────────────────────────────────────────────
#  GAZETTE DATA  (replace with DB query later)
# ─────────────────────────────────────────────
GAZETTE_DATA = {
    "subscriber_name": "Margaret",
    "issue_date": datetime.date(2026, 6, 29),   # coming Sunday
    "columns": [
        {
            "author": "Mom",
            "submitted": True,
            "text": (
                "The garden is finally coming in after that rough patch in May. "
                "I spent most of Tuesday afternoon out there, which is honestly the "
                "best Tuesday I've had in months. The tomatoes are going to be "
                "spectacular this year — I can already tell. Your father keeps sneaking "
                "out to check on them like they might disappear. We're both doing well "
                "and thinking about you constantly. Come visit soon."
            ),
        },
        {
            "author": "Dad",
            "submitted": True,
            "text": (
                "Finished building the new workbench in the garage. Took three weekends "
                "longer than I said it would, but your mother has agreed to stop "
                "bringing that up. It's solid oak and I'm very proud of it. Also caught "
                "a 14-inch bass at the lake Wednesday morning — threw it back, but we "
                "had a good talk first. Life is good out here. Miss you."
            ),
        },
        {
            "author": "Aunt Carol",
            "submitted": False,
            "text": None,
        },
        {
            "author": "Jake",
            "submitted": True,
            "text": (
                "Big news: I finally ran a 5K without stopping. I know that sounds small "
                "but six months ago I couldn't make it to the end of the block. Crossed "
                "the finish line and cried a little, which I'm choosing to blame on the "
                "wind. Also started learning to make pasta from scratch. First attempt "
                "was a disaster but attempt number three was genuinely good. Big week."
            ),
        },
        {
            "author": "Grandma Ruth",
            "submitted": True,
            "text": (
                "We had the Hendersons over for dinner on Thursday and I made the pot "
                "roast. Everyone asked for the recipe and I said I'd write it down but "
                "honestly I never measure anything so that's going to be a creative "
                "document. I've been watching that show you recommended and I have "
                "thoughts. We'll talk on Sunday. I love you more than pot roast, "
                "which is saying something."
            ),
        },
        {
            "author": "Sara",
            "submitted": True,
            "text": (
                "Defended my thesis draft on Monday. It went better than I expected, "
                "which means I only had a small breakdown afterward instead of the "
                "large one I had budgeted for. My advisor said it's nearly there. "
                "Nearly! After two years! I celebrated with a very expensive sandwich "
                "and zero regrets. Almost done. Can almost see the finish line. "
                "Thank you for always checking in — it means more than you know."
            ),
        },
    ]
}

# ─────────────────────────────────────────────
#  COLORS
# ─────────────────────────────────────────────
INK        = colors.HexColor("#1a1714")
MUTED      = colors.HexColor("#7a7063")
RULE_COLOR = colors.HexColor("#c8c0b0")
PAPER      = colors.HexColor("#f7f4ee")
ACCENT     = colors.HexColor("#2b4a2f")

# ─────────────────────────────────────────────
#  HORIZONTAL RULE FLOWABLE
# ─────────────────────────────────────────────
class ThinRule(Flowable):
    def __init__(self, width, thickness=0.5, color=RULE_COLOR, top=4, bottom=4):
        super().__init__()
        self.rule_width = width
        self.thickness  = thickness
        self.color      = color
        self.top        = top
        self.bottom     = bottom

    def wrap(self, *args):
        return self.rule_width, self.thickness + self.top + self.bottom

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.bottom, self.rule_width, self.bottom)


class DoubleRule(Flowable):
    """A double horizontal rule like a classic masthead border."""
    def __init__(self, width, top=4, bottom=4):
        super().__init__()
        self.rule_width = width
        self.top = top
        self.bottom = bottom

    def wrap(self, *args):
        return self.rule_width, 6 + self.top + self.bottom

    def draw(self):
        self.canv.setStrokeColor(INK)
        self.canv.setLineWidth(1.2)
        self.canv.line(0, self.bottom + 4, self.rule_width, self.bottom + 4)
        self.canv.setLineWidth(0.4)
        self.canv.line(0, self.bottom,     self.rule_width, self.bottom)


# ─────────────────────────────────────────────
#  STYLES
# ─────────────────────────────────────────────
def build_styles():
    return {
        "masthead": ParagraphStyle(
            "masthead",
            fontName="Times-Bold",
            fontSize=38,
            leading=42,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "masthead_sub": ParagraphStyle(
            "masthead_sub",
            fontName="Times-Italic",
            fontSize=10,
            leading=14,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow",
            fontName="Courier",
            fontSize=7,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "byline": ParagraphStyle(
            "byline",
            fontName="Times-Bold",
            fontSize=13,
            leading=16,
            textColor=INK,
            spaceAfter=2,
            spaceBefore=8,
        ),
        "byline_label": ParagraphStyle(
            "byline_label",
            fontName="Courier",
            fontSize=7,
            leading=10,
            textColor=MUTED,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=14,
            textColor=INK,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "absent": ParagraphStyle(
            "absent",
            fontName="Times-Italic",
            fontSize=9.5,
            leading=14,
            textColor=MUTED,
            spaceAfter=6,
        ),
    }


# ─────────────────────────────────────────────
#  PAGE SETUP — two-column broadsheet
# ─────────────────────────────────────────────
PAGE_W, PAGE_H = letter
MARGIN_OUTER   = 0.65 * inch
MARGIN_INNER   = 0.5  * inch
GUTTER         = 0.25 * inch
MASTHEAD_H     = 1.5  * inch   # reserved for masthead at top of page 1

USABLE_W = PAGE_W - 2 * MARGIN_OUTER
COL_W    = (USABLE_W - GUTTER) / 2


def masthead_canvas(canvas, doc, data):
    """Draw the masthead on page 1 only."""
    canvas.saveState()

    if doc.page == 1:
        y = PAGE_H - MARGIN_INNER

        # Eyebrow
        canvas.setFont("Courier", 7)
        canvas.setFillColor(MUTED)
        canvas.drawCentredString(PAGE_W / 2, y - 10, "YOUR WEEKLY PAPER FROM THE PEOPLE YOU LOVE MOST")

        # Double top rule
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN_OUTER, y - 15, PAGE_W - MARGIN_OUTER, y - 15)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_OUTER, y - 19, PAGE_W - MARGIN_OUTER, y - 19)

        # Masthead title
        title = f"{data['subscriber_name']}'s Gazette"
        canvas.setFont("Times-Bold", 38)
        canvas.setFillColor(INK)
        canvas.drawCentredString(PAGE_W / 2, y - 52, title)

        # Thin rule below title
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_OUTER, y - 60, PAGE_W - MARGIN_OUTER, y - 60)

        # Date line
        issue_date = data["issue_date"].strftime("%A, %B %-d, %Y").upper()
        contributors = sum(1 for c in data["columns"] if c["submitted"])
        total        = len(data["columns"])
        canvas.setFont("Courier", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN_OUTER, y - 72, issue_date)
        canvas.drawRightString(
            PAGE_W - MARGIN_OUTER, y - 72,
            f"{contributors} OF {total} COLUMNISTS THIS WEEK"
        )

        # Double bottom rule
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN_OUTER, y - 80, PAGE_W - MARGIN_OUTER, y - 80)
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN_OUTER, y - 84, PAGE_W - MARGIN_OUTER, y - 84)

    # Footer on every page
    canvas.setFont("Courier", 7)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(
        PAGE_W / 2, MARGIN_INNER / 2,
        f"Your Gazette  ·  {data['subscriber_name']}'s Edition  ·  "
        f"{data['issue_date'].strftime('%B %-d, %Y')}  ·  Page {doc.page}"
    )

    canvas.restoreState()


# ─────────────────────────────────────────────
#  BUILD PDF
# ─────────────────────────────────────────────
def generate_gazette(data, output_path):
    styles = build_styles()

    # Page 1: columns start below masthead
    frame1_left = Frame(
        MARGIN_OUTER, MARGIN_INNER,
        COL_W, PAGE_H - MARGIN_INNER * 2 - MASTHEAD_H,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="p1_left"
    )
    frame1_right = Frame(
        MARGIN_OUTER + COL_W + GUTTER, MARGIN_INNER,
        COL_W, PAGE_H - MARGIN_INNER * 2 - MASTHEAD_H,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="p1_right"
    )

    # Subsequent pages: full height
    frame_left = Frame(
        MARGIN_OUTER, MARGIN_INNER,
        COL_W, PAGE_H - MARGIN_INNER * 2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="left"
    )
    frame_right = Frame(
        MARGIN_OUTER + COL_W + GUTTER, MARGIN_INNER,
        COL_W, PAGE_H - MARGIN_INNER * 2,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        id="right"
    )

    cb = lambda c, d: masthead_canvas(c, d, data)

    doc = BaseDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN_OUTER,
        rightMargin=MARGIN_OUTER,
        topMargin=MARGIN_INNER,
        bottomMargin=MARGIN_INNER,
    )
    doc.addPageTemplates([
        PageTemplate(id="First", frames=[frame1_left, frame1_right], onPage=cb),
        PageTemplate(id="Later", frames=[frame_left,  frame_right],  onPage=cb),
    ])

    # ── Story ──
    story = []

    # Sort columns — submitted ones first, absent ones at the end
    sorted_columns = sorted(data["columns"], key=lambda c: (0 if c["submitted"] else 1))

    for i, col in enumerate(sorted_columns):
        block = []

        # Vertical rule between columns — drawn via thin spacer trick:
        # actual gutter rule is painted on canvas; here we just space
        block.append(ThinRule(COL_W, thickness=0.5, color=RULE_COLOR, top=6, bottom=0))
        block.append(Paragraph(col["author"], styles["byline"]))
        block.append(Paragraph("THIS WEEK'S COLUMN", styles["byline_label"]))

        if col["submitted"]:
            block.append(Paragraph(col["text"], styles["body"]))
        else:
            block.append(
                Paragraph(
                    f"{col['author']} is taking this week off.",
                    styles["absent"]
                )
            )

        block.append(Spacer(1, 8))
        story.extend(block)

    # Switch to Later template after first page
    from reportlab.platypus import NextPageTemplate
    story.insert(0, NextPageTemplate("Later"))
    # But first page uses First template — set it
    doc.pageTemplates[0].id = "First"

    doc.build(story)
    print(f"✓ Gazette generated: {output_path}")


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    out = "/mnt/user-data/outputs/gazette_sample.pdf"
    generate_gazette(GAZETTE_DATA, out)
