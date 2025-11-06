#!/usr/bin/env python3
"""
Convert README.md to PDF using markdown2 and reportlab
"""

try:
    import markdown2
except ImportError:
    import subprocess
    subprocess.run(['pip3', 'install', 'markdown2', '--quiet'])
    import markdown2

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
except ImportError:
    import subprocess
    subprocess.run(['pip3', 'install', 'reportlab', '--quiet'])
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

from pathlib import Path
import re
from html.parser import HTMLParser

class HTMLToReportLab(HTMLParser):
    """Simple HTML to ReportLab converter"""
    
    def __init__(self):
        super().__init__()
        self.elements = []
        self.styles = getSampleStyleSheet()
        self.current_text = []
        self.in_code = False
        self.in_pre = False
        self.code_blocks = []
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=12,
            spaceBefore=20,
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#0066cc'),
            spaceAfter=10,
            spaceBefore=16,
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
        ))
        
        self.styles.add(ParagraphStyle(
            name='CodeBlock',
            parent=self.styles['Code'],
            fontSize=8,
            leftIndent=20,
            rightIndent=20,
            spaceBefore=10,
            spaceAfter=10,
            backColor=colors.HexColor('#f8f8f8'),
        ))

def simple_md_to_pdf():
    """Convert README.md to PDF using a simpler approach"""
    
    # Read README
    with open('README.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Create PDF
    pdf_file = 'README.pdf'
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch,
    )
    
    # Container for PDF elements
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#0066cc'),
        spaceAfter=12,
        alignment=TA_LEFT,
    )
    
    h2_style = ParagraphStyle(
        'CustomH2',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#0066cc'),
        spaceAfter=10,
    )
    
    h3_style = ParagraphStyle(
        'CustomH3',
        parent=styles['Heading3'],
        fontSize=13,
        spaceAfter=8,
    )
    
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Code'],
        fontSize=8,
        leftIndent=20,
        backColor=colors.HexColor('#f5f5f5'),
        spaceBefore=6,
        spaceAfter=6,
    )
    
    # Parse markdown line by line
    lines = content.split('\n')
    i = 0
    in_code_block = False
    code_lines = []
    
    while i < len(lines):
        line = lines[i]
        
        # Handle code blocks
        if line.startswith('```'):
            if in_code_block:
                # End of code block
                if code_lines:
                    code_text = '\n'.join(code_lines)
                    story.append(Preformatted(code_text, code_style))
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
        
        # Handle headings
        if line.startswith('# '):
            text = line[2:].strip()
            # Remove emoji and special characters
            text = re.sub(r'[^\w\s\-\.\,\:\(\)]', '', text)
            story.append(Paragraph(text, title_style))
            story.append(Spacer(1, 0.1*inch))
        
        elif line.startswith('## '):
            text = line[3:].strip()
            text = re.sub(r'[^\w\s\-\.\,\:\(\)]', '', text)
            story.append(Spacer(1, 0.15*inch))
            story.append(Paragraph(text, h2_style))
        
        elif line.startswith('### '):
            text = line[4:].strip()
            text = re.sub(r'[^\w\s\-\.\,\:\(\)]', '', text)
            story.append(Paragraph(text, h3_style))
        
        elif line.startswith('- ') or line.startswith('* '):
            text = line[2:].strip()
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\\1</b>', text)
            text = re.sub(r'`(.*?)`', r'<font face="Courier">\\1</font>', text)
            text = re.sub(r'[🎥📷🔍📊📍🗺️🎬💾🌐⚡🚀💰📦💵🎯📈🔄⚙️🛠️📚🔧🏆🔒🛡️🔐📜🔑✅⚠️❌📁☁️🗑️🖼️📌🌍🧭🤖📝🎭🗄️🔄💿📱🏢📹📸🧪🔬📊🛍️🎨🎓📚👨‍🏫📞]', '', text)
            story.append(Paragraph('• ' + text, styles['Normal']))
        
        elif line.strip() and not line.startswith('|'):
            # Regular paragraph
            text = line.strip()
            if text:
                text = re.sub(r'\*\*(.*?)\*\*', r'<b>\\1</b>', text)
                text = re.sub(r'`(.*?)`', r'<font face="Courier">\\1</font>', text)
                text = re.sub(r'[🎥📷🔍📊📍🗺️🎬💾🌐⚡🚀💰📦💵🎯📈🔄⚙️🛠️📚🔧🏆🔒🛡️🔐📜🔑✅⚠️❌📁☁️🗑️🖼️📌🌍🧭🤖📝🎭🗄️🔄💿📱🏢📹📸🧪🔬📊🛍️🎨🎓📚👨‍🏫📞]', '', text)
                story.append(Paragraph(text, styles['Normal']))
                story.append(Spacer(1, 0.05*inch))
        
        i += 1
    
    # Build PDF
    print("📄 Converting README.md to PDF...")
    doc.build(story)
    print("✅ Successfully created README.pdf")
    print(f"📍 Location: {Path('README.pdf').absolute()}")

if __name__ == '__main__':
    simple_md_to_pdf()
