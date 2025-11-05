#!/usr/bin/env python3
"""
Enhanced README to PDF Converter
Converts README.md to a professional PDF with:
- Clickable table of contents
- Internal section links
- External URL links
- Embedded images
- Professional styling
"""

import re
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import urllib.request
from io import BytesIO

class NumberedCanvas(canvas.Canvas):
    """Canvas with page numbers and header"""
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.grey)
        self.drawRightString(
            letter[0] - 0.75*inch,
            0.5*inch,
            f"Page {self._pageNumber} of {page_count}"
        )

def remove_emojis(text):
    """Remove emojis from text for PDF compatibility"""
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"  # supplemental symbols
        u"\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

def create_styles():
    """Create custom paragraph styles"""
    styles = getSampleStyleSheet()
    
    # Oracle blue color
    oracle_blue = colors.HexColor('#0066cc')
    oracle_dark = colors.HexColor('#003366')
    
    # Title style
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=oracle_blue,
        spaceAfter=20,
        spaceBefore=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
    ))
    
    # Heading styles with bookmarks
    styles.add(ParagraphStyle(
        name='CustomHeading1',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=oracle_blue,
        spaceAfter=12,
        spaceBefore=16,
        fontName='Helvetica-Bold',
        keepWithNext=True,
    ))
    
    styles.add(ParagraphStyle(
        name='CustomHeading2',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=oracle_dark,
        spaceAfter=10,
        spaceBefore=12,
        fontName='Helvetica-Bold',
        keepWithNext=True,
    ))
    
    styles.add(ParagraphStyle(
        name='CustomHeading3',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=oracle_dark,
        spaceAfter=8,
        spaceBefore=10,
        fontName='Helvetica-Bold',
        keepWithNext=True,
    ))
    
    # Body text style
    styles.add(ParagraphStyle(
        name='CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ))
    
    # Code style
    styles.add(ParagraphStyle(
        name='CustomCode',
        parent=styles['Code'],
        fontSize=8,
        fontName='Courier',
        textColor=colors.HexColor('#333333'),
        backgroundColor=colors.HexColor('#f5f5f5'),
        borderColor=colors.HexColor('#cccccc'),
        borderWidth=1,
        borderPadding=6,
        spaceAfter=10,
        spaceBefore=6,
        leftIndent=10,
        rightIndent=10,
    ))
    
    # Bullet list style
    styles.add(ParagraphStyle(
        name='CustomBullet',
        parent=styles['BodyText'],
        fontSize=10,
        leading=14,
        leftIndent=20,
        bulletIndent=10,
        spaceAfter=4,
    ))
    
    # TOC styles
    styles.add(ParagraphStyle(
        name='TOCHeading1',
        parent=styles['Normal'],
        fontSize=12,
        textColor=oracle_blue,
        fontName='Helvetica-Bold',
        spaceAfter=6,
        leftIndent=0,
    ))
    
    styles.add(ParagraphStyle(
        name='TOCHeading2',
        parent=styles['Normal'],
        fontSize=10,
        textColor=oracle_dark,
        spaceAfter=4,
        leftIndent=20,
    ))
    
    return styles

def process_inline_formatting(text, style_name='CustomBody'):
    """Process inline markdown formatting and convert to reportlab format"""
    # Remove emojis
    text = remove_emojis(text)
    
    # Convert links [text](url) to clickable links
    def replace_link(match):
        link_text = match.group(1)
        url = match.group(2)
        # Check if it's an internal anchor or external URL
        if url.startswith('#'):
            # Internal link - create anchor
            anchor = url[1:]
            return f'<link href="#{anchor}" color="blue"><u>{link_text}</u></link>'
        else:
            # External link
            return f'<link href="{url}" color="blue"><u>{link_text}</u></link>'
    
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', replace_link, text)
    
    # Convert **bold** to <b>bold</b>
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', text)
    
    # Convert `code` to <font name="Courier">code</font>
    text = re.sub(r'`([^`]+)`', r'<font name="Courier" color="#d63384">\1</font>', text)
    
    # Escape special XML characters
    # text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    return text

def download_image(url):
    """Download image from URL and return as ImageReader"""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            image_data = response.read()
            return ImageReader(BytesIO(image_data))
    except Exception as e:
        print(f"⚠️  Could not download image from {url}: {e}")
        return None

def parse_markdown_to_pdf(md_file, output_pdf):
    """Parse markdown and create PDF with links and images"""
    
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_pdf,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=1*inch,
        bottomMargin=0.75*inch,
    )
    
    styles = create_styles()
    story = []
    
    # Track headings for TOC
    toc_entries = []
    heading_counters = {}
    
    # Split content into lines
    lines = content.split('\n')
    i = 0
    in_code_block = False
    code_lines = []
    in_table = False
    table_lines = []
    
    while i < len(lines):
        line = lines[i]
        
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    code_text = remove_emojis(code_text)
                    # Split long code lines
                    code_para = Paragraph(
                        code_text.replace('<', '&lt;').replace('>', '&gt;'),
                        styles['CustomCode']
                    )
                    story.append(code_para)
                code_lines = []
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
            i += 1
            continue
        
        if in_code_block:
            code_lines.append(line)
            i += 1
            continue
        
        # Handle images ![alt](url)
        image_match = re.match(r'!\[([^\]]*)\]\(([^\)]+)\)', line.strip())
        if image_match:
            alt_text = image_match.group(1)
            image_url = image_match.group(2)
            
            # Try to load image
            if image_url.startswith('http'):
                img_reader = download_image(image_url)
                if img_reader:
                    try:
                        img = Image(image_url, width=5*inch, height=3*inch, kind='proportional')
                        story.append(img)
                        if alt_text:
                            caption = Paragraph(
                                f'<i>{remove_emojis(alt_text)}</i>',
                                styles['CustomBody']
                            )
                            story.append(caption)
                        story.append(Spacer(1, 0.2*inch))
                    except Exception as e:
                        print(f"⚠️  Could not embed image: {e}")
            elif os.path.exists(image_url):
                try:
                    img = Image(image_url, width=5*inch, height=3*inch, kind='proportional')
                    story.append(img)
                    if alt_text:
                        caption = Paragraph(
                            f'<i>{remove_emojis(alt_text)}</i>',
                            styles['CustomBody']
                        )
                        story.append(caption)
                    story.append(Spacer(1, 0.2*inch))
                except Exception as e:
                    print(f"⚠️  Could not embed image: {e}")
            
            i += 1
            continue
        
        # Handle headings
        if line.startswith('# '):
            title = line[2:].strip()
            title_clean = remove_emojis(title)
            anchor = re.sub(r'[^a-zA-Z0-9-]', '', title.lower().replace(' ', '-'))
            
            # Add to TOC
            toc_entries.append(('h1', title_clean, anchor))
            
            # Add title with anchor
            para = Paragraph(
                f'<a name="{anchor}"/>{process_inline_formatting(title_clean)}',
                styles['CustomTitle']
            )
            story.append(para)
            story.append(Spacer(1, 0.1*inch))
            
        elif line.startswith('## '):
            heading = line[3:].strip()
            heading_clean = remove_emojis(heading)
            anchor = re.sub(r'[^a-zA-Z0-9-]', '', heading.lower().replace(' ', '-'))
            
            # Add to TOC
            toc_entries.append(('h1', heading_clean, anchor))
            
            para = Paragraph(
                f'<a name="{anchor}"/>{process_inline_formatting(heading_clean)}',
                styles['CustomHeading1']
            )
            story.append(para)
            
        elif line.startswith('### '):
            heading = line[4:].strip()
            heading_clean = remove_emojis(heading)
            anchor = re.sub(r'[^a-zA-Z0-9-]', '', heading.lower().replace(' ', '-'))
            
            # Add to TOC
            toc_entries.append(('h2', heading_clean, anchor))
            
            para = Paragraph(
                f'<a name="{anchor}"/>{process_inline_formatting(heading_clean)}',
                styles['CustomHeading2']
            )
            story.append(para)
            
        elif line.startswith('#### '):
            heading = line[5:].strip()
            heading_clean = remove_emojis(heading)
            anchor = re.sub(r'[^a-zA-Z0-9-]', '', heading.lower().replace(' ', '-'))
            
            para = Paragraph(
                f'<a name="{anchor}"/>{process_inline_formatting(heading_clean)}',
                styles['CustomHeading3']
            )
            story.append(para)
        
        # Handle bullet points
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            bullet_text = line.strip()[2:]
            bullet_text = process_inline_formatting(bullet_text)
            para = Paragraph(f'• {bullet_text}', styles['CustomBullet'])
            story.append(para)
        
        # Handle numbered lists
        elif re.match(r'^\d+\.\s', line.strip()):
            list_text = re.sub(r'^\d+\.\s', '', line.strip())
            list_text = process_inline_formatting(list_text)
            para = Paragraph(list_text, styles['CustomBullet'])
            story.append(para)
        
        # Handle horizontal rules
        elif line.strip() == '---' or line.strip() == '***':
            story.append(Spacer(1, 0.1*inch))
            story.append(Table([['_' * 80]], colWidths=[6.5*inch]))
            story.append(Spacer(1, 0.1*inch))
        
        # Handle regular paragraphs
        elif line.strip():
            para_text = process_inline_formatting(line.strip())
            para = Paragraph(para_text, styles['CustomBody'])
            story.append(para)
        
        # Handle empty lines
        else:
            story.append(Spacer(1, 0.05*inch))
        
        i += 1
    
    # Insert TOC at the beginning if we have entries
    if toc_entries:
        toc_story = []
        toc_story.append(Paragraph(
            '<a name="table-of-contents"/>Table of Contents',
            styles['CustomTitle']
        ))
        toc_story.append(Spacer(1, 0.2*inch))
        
        for level, title, anchor in toc_entries[:20]:  # Limit TOC to first 20 entries
            if level == 'h1':
                toc_para = Paragraph(
                    f'<link href="#{anchor}" color="blue"><u>{title}</u></link>',
                    styles['TOCHeading1']
                )
            else:
                toc_para = Paragraph(
                    f'<link href="#{anchor}" color="blue"><u>{title}</u></link>',
                    styles['TOCHeading2']
                )
            toc_story.append(toc_para)
        
        toc_story.append(PageBreak())
        
        # Insert TOC at the beginning
        story = toc_story + story
    
    # Build PDF
    print("📄 Converting README.md to enhanced PDF with links and images...")
    doc.build(story, canvasmaker=NumberedCanvas)
    print("✅ Successfully created enhanced README.pdf")
    print(f"📍 Location: {os.path.abspath(output_pdf)}")
    print(f"✨ Features: Clickable TOC, internal links, external URLs, page numbers")

if __name__ == '__main__':
    parse_markdown_to_pdf('README.md', 'README.pdf')
