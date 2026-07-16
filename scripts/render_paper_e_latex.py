#!/usr/bin/env python3
"""Minimal, stdlib-only Markdown -> LaTeX renderer for Paper E (self-falsification case report).

Sibling of render_paper_d_latex.py, adapted for Paper E's layout: `##` section
headings, an inline `## References` bullet list (kept, not replaced), and its
own citation-key map. ASCII-only LaTeX output; compiles with plain pdflatex.

Usage:
    render_paper_e_latex.py INPUT.md OUTPUT.tex
then run pdflatex twice on OUTPUT.tex.
"""
import re
import sys

CITES = {
    "Sharma2023": "Sharma et al.\\ 2023",
    "Stechly2023": "Stechly et al.\\ 2023",
    "McAleese2024": "McAleese et al.\\ 2024",
    "Du2023": "Du et al.\\ 2023",
    "Nosek2018": "Nosek et al.\\ 2018",
    "Szollosi2020": "Szollosi et al.\\ 2020",
    "KleinRoodman2005": "Klein \\& Roodman 2005",
    "MacCounPerlmutter2015": "MacCoun \\& Perlmutter 2015",
}

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage[colorlinks=true,urlcolor=blue,linkcolor=blue,citecolor=blue]{hyperref}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}
\hypersetup{pdftitle={The Audit That Bit Its Master}}
"""

# Map the non-ASCII characters used in main.md to LaTeX (ASCII output only).
UNI = [("–", "--"), ("—", "---"), ("…", r"\ldots{}"), ("≠", r"$\neq$"),
       ("Λ", r"$\Lambda$"), ("σ", r"$\sigma$"), ("→", r"$\rightarrow$"),
       ("§", r"\S{}"), ("≈", r"$\approx$")]


def ulatex(s):
    for a, b in UNI:
        s = s.replace(a, b)
    return s


def esc(t):
    t = t.replace("\\", r"\textbackslash{}")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}"), ("$", r"\$")]:
        t = t.replace(a, b)
    return t


def cite_sub(m):
    keys = [k.strip().lstrip("@").replace("\\_", "_") for k in m.group(1).split(";")]
    return "(" + "; ".join(CITES.get(k, k) for k in keys) + ")"


def inline(text):
    codes, maths = [], []

    def grab_code(m):
        codes.append(m.group(1))
        return f"\x00{len(codes)-1}\x00"

    def grab_math(m):
        maths.append(m.group(1))
        return f"\x01{len(maths)-1}\x01"

    text = re.sub(r"`([^`]+)`", grab_code, text)
    text = re.sub(r"\$([^$]+)\$", grab_math, text)
    text = esc(text)
    text = ulatex(text)
    text = re.sub(r"\[([^\]]*@[^\]]+)\]", cite_sub, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", text)
    for i, c in enumerate(maths):
        text = text.replace(f"\x01{i}\x01", f"${c}$")
    for i, c in enumerate(codes):
        text = text.replace(f"\x00{i}\x00", r"\texttt{" + ulatex(esc(c)) + "}")
    return text


def convert(md):
    body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)
    blocks = re.split(r"\n\s*\n", body.strip())
    out = []
    for blk in blocks:
        lines = blk.splitlines()
        if not lines:
            continue
        h = re.match(r"^(#{1,3})\s+(.*)$", lines[0])
        if h:
            head = h.group(2).strip()
            out.append(r"\section*{" + inline(head) + "}")
            rest = [l for l in lines[1:] if l.strip()]
            if rest and all(re.match(r"^- ", l) for l in rest):
                out.append(r"\begin{itemize}")
                for l in rest:
                    out.append(r"\item " + inline(l.strip()[2:]))
                out.append(r"\end{itemize}")
            elif rest:
                out.append(inline(" ".join(rest)))
        elif all(re.match(r"^- ", l) for l in lines if l.strip()):
            out.append(r"\begin{itemize}")
            for l in lines:
                if l.strip():
                    out.append(r"\item " + inline(l.strip()[2:]))
            out.append(r"\end{itemize}")
        elif all(re.match(r"^\d+\. ", l) for l in lines if l.strip()):
            out.append(r"\begin{enumerate}")
            for l in lines:
                if l.strip():
                    out.append(r"\item " + inline(re.sub(r"^\d+\.\s*", "", l.strip())))
            out.append(r"\end{enumerate}")
        else:
            out.append(inline(" ".join(l.strip() for l in lines)))
    return "\n\n".join(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    md = open(src, encoding="utf-8").read()
    tm = re.search(r"^title:\s*'(.*)'\s*$", md, re.MULTILINE)
    title = tm.group(1).replace("''", "'") if tm else "Paper E"
    dm = re.search(r"^date:\s*(.+)$", md, re.MULTILINE)
    date = dm.group(1).strip() if dm else ""
    title_block = (
        r"\title{" + ulatex(esc(title)) + "}" + "\n"
        r"\author{Dimitar Baev\thanks{ORCID: \href{https://orcid.org/0009-0009-7812-9203}{0009-0009-7812-9203}} \\"
        r" \normalsize Independent researcher; Founder, Monster Cleaning Ltd. (\url{https://monstercleaning.com})}" + "\n"
        r"\date{" + esc(date) + "}"
    )
    doc = (PREAMBLE + title_block + "\n\\begin{document}\n\\maketitle\n\n"
           + convert(md) + "\n\\end{document}\n")
    open(dst, "w", encoding="utf-8").write(doc)
    print(f"wrote {dst} ({len(doc)} bytes)")


if __name__ == "__main__":
    main()
