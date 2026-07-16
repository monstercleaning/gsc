#!/usr/bin/env python3
"""Minimal, stdlib-only Markdown -> LaTeX renderer for the Paper D JOSS summary.

Tailored to the limited Markdown subset used in `paper.md` (headings,
paragraphs, **bold**, *italic*, `inline code`, bullet/numbered lists,
[@cite] citations, and $math$). Produces a clean preprint PDF via xelatex
without requiring pandoc or Docker.

Usage:
    render_paper_d_latex.py INPUT.md OUTPUT.tex
then:
    xelatex -interaction=nonstopmode OUTPUT.tex   (run twice)
"""
import re
import sys

CITES = {
    "OpenScienceFramework": "Open Science Framework",
    "LIGO_Open_Science": "LIGO Open Science Center",
    "AllPrePost": "ClinicalTrials.gov",
    "Nosek": "Nosek et al.\\ 2018",
    "Wetterich2013": "Wetterich 2013",
    "CanutoEtAl1977": "Canuto et al.\\ 1977",
    "Reuter1998": "Reuter 1998",
    "PercacciSaueressig2017": "Percacci \\& Saueressig 2017",
}

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=1in]{geometry}
\usepackage{amsmath}
\usepackage[colorlinks=true,urlcolor=blue,linkcolor=blue,citecolor=blue]{hyperref}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}
\hypersetup{pdftitle={GSC: A Pre-Registration Reproducibility Stack}}
"""

# Map the handful of non-ASCII characters used in paper.md to LaTeX, so the
# output is ASCII and compiles with plain pdflatex (no fontspec/newunicodechar).
UNI = [("Λ", r"$\Lambda$"), ("θ", r"$\theta$"), ("σ", r"$\sigma$"),
       ("→", r"$\rightarrow$"), ("↔", r"$\leftrightarrow$"),
       ("–", "--"), ("—", "---")]


def ulatex(s):
    for a, b in UNI:
        s = s.replace(a, b)
    return s

REFERENCES = r"""\section*{References}
\small
\begin{enumerate}
\item B. A. Nosek, C. R. Ebersole, A. C. DeHaven, D. T. Mellor, ``The preregistration revolution,'' \emph{PNAS} \textbf{115}(11), 2600--2606 (2018). \href{https://doi.org/10.1073/pnas.1708274114}{doi:10.1073/pnas.1708274114}.
\item Open Science Framework --- preregistration in scientific practice, Center for Open Science. \url{https://osf.io/preregistration}.
\item ClinicalTrials.gov: registration of clinical investigations, U.S. National Library of Medicine. \url{https://clinicaltrials.gov}.
\item LIGO Open Science Center: pre-registered analysis pipelines for gravitational-wave events. \url{https://www.gw-openscience.org}.
\item C. Wetterich, ``A Universe without expansion,'' \emph{Physics of the Dark Universe} \textbf{2}(4), 184--187 (2013). \href{https://doi.org/10.1016/j.dark.2013.10.002}{doi:10.1016/j.dark.2013.10.002}; arXiv:1303.6878.
\item V. Canuto, P. J. Adams, S.-H. Hsieh, E. Tsiang, ``Scale-covariant theory of gravitation and astrophysical applications,'' \emph{Phys. Rev. D} \textbf{16}, 1643--1663 (1977). \href{https://doi.org/10.1103/PhysRevD.16.1643}{doi:10.1103/PhysRevD.16.1643}.
\item M. Reuter, ``Nonperturbative evolution equation for quantum gravity,'' \emph{Phys. Rev. D} \textbf{57}, 971--985 (1998). \href{https://doi.org/10.1103/PhysRevD.57.971}{doi:10.1103/PhysRevD.57.971}.
\item R. Percacci, F. Saueressig, \emph{An Introduction to Covariant Quantum Gravity and Asymptotic Safety}, World Scientific (2017). \href{https://doi.org/10.1142/10369}{doi:10.1142/10369}.
\end{enumerate}
"""


def esc(t):
    """Escape LaTeX specials in plain text. Unicode is left for newunicodechar."""
    t = t.replace("\\", r"\textbackslash{}")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"),
                 ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}"), ("$", r"\$")]:
        t = t.replace(a, b)
    return t


def cite_sub(m):
    # esc() runs before this, so underscores arrive as "\_"; undo for lookup.
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
    # strip front-matter
    body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)
    blocks = re.split(r"\n\s*\n", body.strip())
    out = []
    for blk in blocks:
        lines = blk.splitlines()
        if not lines:
            continue
        if lines[0].startswith("# "):
            head = lines[0][2:].strip()
            if head.lower() == "references":
                continue  # replaced by manual bibliography
            out.append(r"\section*{" + ulatex(esc(head)) + "}")
            rest = [l for l in lines[1:] if l.strip()]
            if rest:
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
    fm = re.search(r"title:\s*'([^']+)'", md)
    title = fm.group(1) if fm else "GSC"
    datem = re.search(r"date:\s*(.+)", md)
    date = datem.group(1).strip() if datem else ""
    title_block = (
        r"\title{" + esc(title) + "}" + "\n"
        r"\author{Dimitar Baev\thanks{ORCID: \href{https://orcid.org/0009-0009-7812-9203}{0009-0009-7812-9203}} \\"
        r" \normalsize Independent researcher; Founder, Monster Cleaning Ltd. (\url{https://monstercleaning.com})}" + "\n"
        r"\date{" + esc(date) + "}"
    )
    doc = (PREAMBLE + title_block + "\n\\begin{document}\n\\maketitle\n\n"
           + convert(md) + "\n\n" + REFERENCES + "\n\\end{document}\n")
    open(dst, "w", encoding="utf-8").write(doc)
    print(f"wrote {dst} ({len(doc)} bytes)")


if __name__ == "__main__":
    main()
