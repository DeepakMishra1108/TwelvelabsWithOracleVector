#!/usr/bin/env python3
"""
Complete README to PDF Converter with Tables and Images
Uses markdown library with proper HTML/CSS for professional output
"""

import markdown
import re
import os
from io import BytesIO

# Set library path for WeasyPrint to find Pango/Cairo on macOS
if 'DYLD_LIBRARY_PATH' not in os.environ:
    os.environ['DYLD_LIBRARY_PATH'] = '/opt/homebrew/lib'

def create_html_with_styles(md_content):
    """Convert markdown to styled HTML"""
    
    # Configure markdown with extensions for tables, code blocks, etc.
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        'codehilite',
        'toc',
        'attr_list',
        'def_list',
        'abbr',
        'footnotes',
        'md_in_html'
    ])
    
    # Convert markdown to HTML
    html_content = md.convert(md_content)
    
    # Generate table of contents
    toc_html = md.toc if hasattr(md, 'toc') else ""
    
    # Create complete HTML document with professional styling
    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TwelveLabs AI Platform with Oracle Vector Database</title>
    <style>
        @page {{
            size: letter;
            margin: 0.75in;
            @bottom-right {{
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }}
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.6;
            color: #333;
            max-width: 100%;
        }}
        
        h1 {{
            color: #0066cc;
            font-size: 24pt;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
            margin-top: 20px;
            margin-bottom: 15px;
            page-break-after: avoid;
        }}
        
        h2 {{
            color: #0066cc;
            font-size: 18pt;
            border-bottom: 2px solid #0066cc;
            padding-bottom: 8px;
            margin-top: 18px;
            margin-bottom: 12px;
            page-break-after: avoid;
        }}
        
        h3 {{
            color: #003366;
            font-size: 14pt;
            margin-top: 15px;
            margin-bottom: 10px;
            page-break-after: avoid;
        }}
        
        h4 {{
            color: #003366;
            font-size: 12pt;
            margin-top: 12px;
            margin-bottom: 8px;
            page-break-after: avoid;
        }}
        
        p {{
            margin: 8px 0;
            text-align: justify;
        }}
        
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        
        a:hover {{
            text-decoration: underline;
        }}
        
        code {{
            background-color: #f5f5f5;
            color: #d63384;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 9pt;
        }}
        
        pre {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-left: 4px solid #0066cc;
            padding: 12px;
            overflow-x: auto;
            border-radius: 4px;
            margin: 12px 0;
            page-break-inside: avoid;
        }}
        
        pre code {{
            background-color: transparent;
            padding: 0;
            color: #333;
            font-size: 8pt;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
            font-size: 9pt;
            page-break-inside: avoid;
        }}
        
        table th {{
            background-color: #0066cc;
            color: white;
            padding: 10px;
            text-align: left;
            font-weight: bold;
            border: 1px solid #0052a3;
        }}
        
        table td {{
            padding: 8px;
            border: 1px solid #dee2e6;
        }}
        
        table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        table tr:hover {{
            background-color: #e9ecef;
        }}
        
        ul, ol {{
            margin: 10px 0;
            padding-left: 25px;
        }}
        
        li {{
            margin: 5px 0;
        }}
        
        blockquote {{
            border-left: 4px solid #0066cc;
            padding-left: 15px;
            margin: 15px 0;
            color: #666;
            font-style: italic;
        }}
        
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 15px auto;
            border: 1px solid #dee2e6;
            border-radius: 4px;
        }}
        
        hr {{
            border: none;
            border-top: 2px solid #dee2e6;
            margin: 20px 0;
        }}
        
        .toc {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
            page-break-after: always;
        }}
        
        .toc h2 {{
            margin-top: 0;
            color: #0066cc;
            border-bottom: 2px solid #0066cc;
        }}
        
        .toc ul {{
            list-style: none;
            padding-left: 0;
        }}
        
        .toc li {{
            margin: 8px 0;
        }}
        
        .toc a {{
            color: #0066cc;
            text-decoration: none;
        }}
        
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            background-color: #0066cc;
            color: white;
            border-radius: 3px;
            font-size: 8pt;
            font-weight: bold;
            margin: 2px;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .header h1 {{
            color: #0066cc;
            font-size: 28pt;
            margin-bottom: 10px;
            border-bottom: none;
        }}
        
        .header p {{
            color: #666;
            font-size: 12pt;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>TwelveLabs AI Platform with Oracle Vector Database</h1>
        <p>Advanced Media Intelligence Platform powered by Oracle Cloud Infrastructure</p>
    </div>
    
    {f'<div class="toc"><h2>Table of Contents</h2>{toc_html}</div>' if toc_html else ''}
    
    {html_content}
    
    <hr>
    <p style="text-align: center; color: #666; font-size: 9pt; margin-top: 30px;">
        Generated from README.md | Oracle Cloud Infrastructure | TwelveLabs Platform
    </p>
</body>
</html>
"""
    
    return html_template

def markdown_to_pdf_html(md_file, output_pdf):
    """Convert markdown to PDF using HTML intermediate"""
    
    print("📄 Converting README.md to professional PDF...")
    print("   ├─ Reading markdown file...")
    
    # Read markdown file
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    print("   ├─ Converting markdown to HTML...")
    
    # Convert to HTML with styles
    html_content = create_html_with_styles(md_content)
    
    # Save HTML for debugging (optional)
    html_file = md_file.replace('.md', '.html')
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"   ├─ Created HTML: {html_file}")
    
    # Try to convert to PDF using WeasyPrint
    try:
        print("   ├─ Attempting PDF generation with WeasyPrint...")
        from weasyprint import HTML, CSS
        
        HTML(string=html_content).write_pdf(
            output_pdf,
            stylesheets=[CSS(string='''
                @page { margin: 0.75in; }
            ''')]
        )
        
        print(f"✅ Successfully created {output_pdf}")
        print(f"📍 Location: {os.path.abspath(output_pdf)}")
        print(f"✨ Features: Tables, links, styling, proper formatting")
        return True
        
    except Exception as e:
        print(f"⚠️  WeasyPrint failed: {e}")
        print(f"💡 HTML version saved: {html_file}")
        print(f"💡 You can:")
        print(f"   1. Open {html_file} in a browser and print to PDF")
        print(f"   2. Install wkhtmltopdf: brew install wkhtmltopdf")
        print(f"   3. Use online converter with the HTML file")
        return False

if __name__ == '__main__':
    success = markdown_to_pdf_html('README.md', 'README.pdf')
    if not success:
        print("\n📝 Note: HTML file has been created with all formatting.")
        print("   Open README.html in your browser and use 'Print to PDF' for best results.")
