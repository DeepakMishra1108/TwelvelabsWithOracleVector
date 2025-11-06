#!/usr/bin/env python3
"""
Convert README.md to PDF with proper formatting
"""

import markdown
from weasyprint import HTML, CSS
from pathlib import Path

def convert_readme_to_pdf():
    """Convert README.md to README.pdf"""
    
    # Read README.md
    readme_path = Path('README.md')
    with open(readme_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Convert Markdown to HTML with extensions
    md = markdown.Markdown(extensions=[
        'extra',
        'codehilite',
        'tables',
        'fenced_code',
        'toc'
    ])
    html_content = md.convert(markdown_content)
    
    # Create styled HTML document
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Media Intelligence Platform with Oracle Cloud Infrastructure</title>
        <style>
            @page {{
                size: letter;
                margin: 0.75in;
                @bottom-center {{
                    content: "Page " counter(page) " of " counter(pages);
                    font-size: 10pt;
                    color: #666;
                }}
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
                max-width: 100%;
            }}
            
            h1 {{
                color: #0066cc;
                font-size: 24pt;
                margin-top: 20pt;
                margin-bottom: 10pt;
                page-break-after: avoid;
                border-bottom: 2px solid #0066cc;
                padding-bottom: 8pt;
            }}
            
            h2 {{
                color: #0066cc;
                font-size: 18pt;
                margin-top: 16pt;
                margin-bottom: 8pt;
                page-break-after: avoid;
                border-bottom: 1px solid #ddd;
                padding-bottom: 6pt;
            }}
            
            h3 {{
                color: #333;
                font-size: 14pt;
                margin-top: 12pt;
                margin-bottom: 6pt;
                page-break-after: avoid;
            }}
            
            h4 {{
                color: #555;
                font-size: 12pt;
                margin-top: 10pt;
                margin-bottom: 5pt;
                page-break-after: avoid;
            }}
            
            p {{
                margin-bottom: 8pt;
            }}
            
            code {{
                background-color: #f5f5f5;
                padding: 2pt 4pt;
                border-radius: 3pt;
                font-family: 'Courier New', Consolas, Monaco, monospace;
                font-size: 9pt;
                color: #d14;
            }}
            
            pre {{
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4pt;
                padding: 12pt;
                overflow-x: auto;
                page-break-inside: avoid;
                margin: 10pt 0;
            }}
            
            pre code {{
                background-color: transparent;
                padding: 0;
                color: #333;
                font-size: 9pt;
            }}
            
            ul, ol {{
                margin-bottom: 10pt;
                padding-left: 25pt;
            }}
            
            li {{
                margin-bottom: 4pt;
            }}
            
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 10pt 0;
                page-break-inside: avoid;
                font-size: 10pt;
            }}
            
            th {{
                background-color: #0066cc;
                color: white;
                padding: 8pt;
                text-align: left;
                font-weight: bold;
            }}
            
            td {{
                border: 1px solid #ddd;
                padding: 8pt;
            }}
            
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            
            blockquote {{
                border-left: 4px solid #0066cc;
                padding-left: 12pt;
                margin-left: 0;
                color: #666;
                font-style: italic;
            }}
            
            a {{
                color: #0066cc;
                text-decoration: none;
            }}
            
            strong {{
                color: #000;
                font-weight: 600;
            }}
            
            .emoji {{
                font-size: 12pt;
            }}
            
            hr {{
                border: none;
                border-top: 1px solid #ddd;
                margin: 20pt 0;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Convert HTML to PDF
    print("📄 Converting README.md to PDF...")
    HTML(string=styled_html).write_pdf('README.pdf')
    print("✅ Successfully created README.pdf")
    print(f"📍 Location: {Path('README.pdf').absolute()}")

if __name__ == '__main__':
    convert_readme_to_pdf()
