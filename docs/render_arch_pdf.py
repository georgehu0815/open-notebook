#!/usr/bin/env python3
"""
Pre-renders Mermaid diagrams in ARCHITECTURE.md as PNGs,
then generates a PDF-ready markdown and a final PDF.
"""

import re
import subprocess
import os
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).parent
SRC_MD = DOCS_DIR / "ARCHITECTURE.md"
DIAGRAMS_DIR = DOCS_DIR / "arch-diagrams"
PDF_MD = DOCS_DIR / "ARCHITECTURE_pdf.md"
PDF_OUT = DOCS_DIR / "ARCHITECTURE.pdf"

DIAGRAMS_DIR.mkdir(exist_ok=True)

src = SRC_MD.read_text()

diagram_counter = [0]

def render_mermaid(code: str, label: str) -> str:
    """Render mermaid code block to PNG, return markdown image tag."""
    idx = diagram_counter[0]
    diagram_counter[0] += 1
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    mmd_file = DIAGRAMS_DIR / f"diag-{idx:02d}-{slug}.mmd"
    png_file = DIAGRAMS_DIR / f"diag-{idx:02d}-{slug}.png"

    mmd_file.write_text(code)

    # Determine dimensions based on diagram type
    width = 1400
    height = 1000
    if code.strip().startswith("sequenceDiagram"):
        height = 1200
    elif "erDiagram" in code:
        width = 1600
        height = 1400

    result = subprocess.run(
        ["mmdc", "-i", str(mmd_file), "-o", str(png_file),
         "-t", "neutral", "-b", "white",
         "--width", str(width), "--height", str(height)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: mmdc failed for diagram {idx}: {result.stderr[:200]}", file=sys.stderr)
        return f"*(diagram rendering failed)*"

    rel_path = png_file.relative_to(DOCS_DIR)
    print(f"  Rendered: {rel_path}")
    return f"![Architecture Diagram {idx}]({rel_path})"

# Track context of what section we're in for labeling
current_section = "overview"
output_lines = []
lines = src.split("\n")
i = 0

while i < len(lines):
    line = lines[i]

    # Track section headings for diagram labels
    if line.startswith("## "):
        current_section = line.lstrip("# ").strip()

    # Detect mermaid code fence
    if line.strip() == "```mermaid":
        code_lines = []
        i += 1
        while i < len(lines) and lines[i].strip() != "```":
            code_lines.append(lines[i])
            i += 1
        mermaid_code = "\n".join(code_lines)
        img_tag = render_mermaid(mermaid_code, current_section)
        output_lines.append("")
        output_lines.append(img_tag)
        output_lines.append("")
    else:
        output_lines.append(line)

    i += 1

# Write the PDF-ready markdown
PDF_MD.write_text("\n".join(output_lines))
print(f"\nWrote: {PDF_MD}")

# Generate PDF using pandoc + xelatex
print("\nGenerating PDF...")
result = subprocess.run(
    [
        "pandoc", str(PDF_MD),
        "-o", str(PDF_OUT),
        "--pdf-engine=xelatex",
        "-V", "geometry:margin=2cm",
        "-V", "fontsize=10pt",
        "-V", "papersize=a4",
        "-V", "colorlinks=true",
        "-V", "linkcolor=blue",
        "-V", "urlcolor=blue",
        "--toc",
        "--toc-depth=2",
        "--highlight-style=tango",
        "-V", "monofont=Courier New",
        "--from=markdown+pipe_tables+raw_html",
    ],
    capture_output=True, text=True, cwd=str(DOCS_DIR)
)

if result.returncode == 0:
    size = PDF_OUT.stat().st_size / 1024
    print(f"PDF generated: {PDF_OUT} ({size:.0f} KB)")
else:
    print("PDF generation failed:", file=sys.stderr)
    print(result.stdout[-1000:])
    print(result.stderr[-2000:], file=sys.stderr)
    sys.exit(1)
