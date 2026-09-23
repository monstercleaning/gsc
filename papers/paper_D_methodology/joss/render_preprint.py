#!/usr/bin/env python3
"""Render the JOSS paper (paper.md + paper.bib) to a clean preprint PDF.

The official route is the `joss-paper-d` workflow (openjournals draft action),
whose output carries a DRAFT watermark. This renderer produces the preprint
intended for deposit on Zenodo and figshare: standard-library Python plus
xelatex, no pandoc or Docker.

It handles the Markdown subset paper.md uses (headings, paragraphs, **bold**,
*italic*, `code`, bullet and numbered lists, [@key; @key] citations, $math$).
Citations and the reference list come from paper.bib, so the PDF cannot cite a
work the bibliography does not contain or list one the paper does not cite. An
unknown citation key is an error.

Usage:
    python3 papers/paper_D_methodology/joss/render_preprint.py            # writes paper.tex
    python3 papers/paper_D_methodology/joss/render_preprint.py --pdf      # also runs xelatex twice
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Non-ASCII characters used in paper.md, mapped to LaTeX.
UNICODE = [("Λ", r"$\Lambda$"), ("θ", r"$\theta$"), ("σ", r"$\sigma$"), ("→", r"$\rightarrow$"),
           ("↔", r"$\leftrightarrow$"), ("–", "--"), ("—", "---")]


def to_latex_unicode(s: str) -> str:
    for a, b in UNICODE:
        s = s.replace(a, b)
    return s


def escape(t: str) -> str:
    t = t.replace("\\", r"\textbackslash{}")
    for a, b in [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"), ("}", r"\}"),
                 ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}"), ("$", r"\$")]:
        t = t.replace(a, b)
    return t


# --------------------------------------------------------------------------
# BibTeX (the simple subset paper.bib uses)
# --------------------------------------------------------------------------

def _braced(text: str, i: int):
    """Return (content, index after the closing brace) for a brace group starting at text[i] == '{'."""
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces in paper.bib")


_FIELD = re.compile(r"\s*,?\s*(\w+)\s*=\s*")
_BARE_VALUE = re.compile(r"[^,}\n]*")


def _fields(body: str) -> dict:
    """Read `name = {value}` / `name = "value"` / `name = value` pairs in order."""
    fields, i = {}, 0
    while True:
        m = _FIELD.match(body, i)
        if not m:
            return fields
        j = m.end()
        if j < len(body) and body[j] == "{":
            value, j = _braced(body, j)
        elif j < len(body) and body[j] == '"':
            k = body.index('"', j + 1)
            value, j = body[j + 1:k], k + 1
        else:
            bare = _BARE_VALUE.match(body, j)
            value, j = bare.group(0), bare.end()
        fields[m.group(1).lower()] = value.strip()
        i = j


def parse_bib(text: str) -> dict:
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        body, _ = _braced(text, text.index("{", m.start()))
        entries[m.group(2)] = dict(_fields(body[body.index(",") + 1:]), _type=m.group(1).lower())
    return entries


def _strip_braces(s: str) -> str:
    return s.replace("{", "").replace("}", "")


def _people(field: str):
    """'Last, F. and Last2, G.' -> [('F.', 'Last'), ('G.', 'Last2')]."""
    out = []
    for name in re.split(r"\s+and\s+", field.strip()):
        if "," in name:
            last, first = [x.strip() for x in name.split(",", 1)]
        else:
            parts = name.split()
            first, last = " ".join(parts[:-1]), parts[-1]
        out.append((_strip_braces(first), _strip_braces(last)))
    return out


def cite_label(entry: dict) -> str:
    """In-text label: 'Wetterich 2013', 'Klein & Roodman 2005', 'Nosek et al. 2018', or a short title."""
    if "author" in entry:
        names = [last for _, last in _people(entry["author"])]
        who = names[0] if len(names) == 1 else (f"{names[0]} & {names[1]}" if len(names) == 2
                                                  else f"{names[0]} et al.")
        return f"{who} {entry.get('year', '')}".strip()
    title = _strip_braces(entry.get("title", "?"))
    return re.split(r"\s*[:—]\s*", title, maxsplit=1)[0]


def _url(entry: dict) -> str:
    m = re.search(r"\\url\{([^}]*)\}", entry.get("howpublished", "")) or re.search(r"(https?://\S+)", entry.get("url", ""))
    return m.group(1) if m else ""


def format_reference(entry: dict) -> str:
    bits = []
    if "author" in entry:
        bits.append(", ".join(f"{first} {last}".strip() for first, last in _people(entry["author"])) + ",")
    title = to_latex_unicode(escape(_strip_braces(entry.get("title", ""))))
    kind = entry["_type"]
    if kind == "book":
        bits.append(r"\emph{" + title + "},")
        bits.append(f"{escape(entry.get('publisher', ''))} ({entry.get('year', '')}).")
    elif kind == "article":
        bits.append(f"``{title},''")
        journal = r"\emph{" + escape(entry.get("journal", "")) + "}"
        vol = r" \textbf{" + entry["volume"] + "}" if "volume" in entry else ""
        num = f"({entry['number']})" if "number" in entry else ""
        pages = f", {entry['pages']}" if "pages" in entry else ""
        bits.append(f"{journal}{vol}{num}{pages} ({entry.get('year', '')}).")
    else:
        note = to_latex_unicode(escape(_strip_braces(entry.get("note", ""))))
        bits.append(title + (f", {note}." if note else "."))
    if "doi" in entry:
        doi = entry["doi"]
        bits.append(r"\href{https://doi.org/" + doi + "}{doi:" + escape(doi) + "}.")
    if entry.get("archiveprefix", "").lower() == "arxiv" and "eprint" in entry:
        bits.append(f"arXiv:{entry['eprint']}.")
    url = _url(entry)
    if url:
        bits.append(r"\url{" + url + "}.")
    return " ".join(bits)


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

class Renderer:
    def __init__(self, bib: dict):
        self.bib = bib
        self.cited: list = []

    def _cite(self, m) -> str:
        keys = [k.strip().lstrip("@").replace("\\_", "_") for k in m.group(1).split(";")]
        labels = []
        for k in keys:
            if k not in self.bib:
                raise KeyError(f"citation @{k} is not in paper.bib")
            if k not in self.cited:
                self.cited.append(k)
            labels.append(escape(cite_label(self.bib[k])).replace("et al. ", "et al.\\ "))
        return "(" + "; ".join(labels) + ")"

    def inline(self, text: str) -> str:
        codes, maths = [], []
        text = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes) - 1}\x00", text)
        text = re.sub(r"\$([^$]+)\$", lambda m: maths.append(m.group(1)) or f"\x01{len(maths) - 1}\x01", text)
        text = to_latex_unicode(escape(text))
        text = re.sub(r"\[([^\]]*@[^\]]+)\]", self._cite, text)
        text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\\emph{\1}", text)
        for i, c in enumerate(maths):
            text = text.replace(f"\x01{i}\x01", f"${c}$")
        for i, c in enumerate(codes):
            text = text.replace(f"\x00{i}\x00", r"\texttt{" + to_latex_unicode(escape(c)) + "}")
        return text

    def body(self, md: str) -> str:
        body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)
        out = []
        for block in re.split(r"\n\s*\n", body.strip()):
            lines = [l for l in block.splitlines() if l.strip()]
            if not lines:
                continue
            if lines[0].startswith("# "):
                head = lines[0][2:].strip()
                if head.lower() == "references":
                    continue
                out.append(r"\section*{" + to_latex_unicode(escape(head)) + "}")
                if lines[1:]:
                    out.append(self.inline(" ".join(lines[1:])))
            elif all(l.startswith("- ") for l in lines):
                out += [r"\begin{itemize}"] + [r"\item " + self.inline(l[2:].strip()) for l in lines] + [r"\end{itemize}"]
            elif all(re.match(r"^\d+\. ", l) for l in lines):
                out += ([r"\begin{enumerate}"] + [r"\item " + self.inline(re.sub(r"^\d+\.\s*", "", l)) for l in lines]
                        + [r"\end{enumerate}"])
            else:
                out.append(self.inline(" ".join(l.strip() for l in lines)))
        return "\n\n".join(out)


def front_matter(md: str) -> dict:
    fm = re.match(r"^---\n(.*?)\n---", md, re.DOTALL).group(1)
    get = lambda pat: (re.search(pat, fm, re.MULTILINE) or [None, ""])[1].strip().strip("'\"")
    return {
        "title": get(r"^title:\s*(.+)$"),
        "date": get(r"^date:\s*(.+)$"),
        "author": get(r"^\s*-\s*name:\s*(.+)$"),
        "orcid": get(r"^\s*orcid:\s*(.+)$"),
        "affiliation": (re.findall(r"^\s*-\s*name:\s*(.+)$", fm, re.MULTILINE) or ["", ""])[-1].strip().strip("'\""),
        "tags": [t.strip() for t in re.findall(r"^\s*-\s+([^:\n]+)$", fm.split("authors:")[0], re.MULTILINE)],
    }


def render(md: str, bib_text: str) -> str:
    meta = front_matter(md)
    r = Renderer(parse_bib(bib_text))
    body = r.body(md)
    refs = "\n".join(r"\item " + format_reference(r.bib[k]) for k in r.cited)
    affiliation = escape(re.sub(r"\s*\((https?://[^)]+)\)", "", meta["affiliation"]))
    url = re.search(r"\((https?://[^)]+)\)", meta["affiliation"])
    keywords = ", ".join(t for t in meta["tags"] if t.lower() != "python")
    preamble = "\n".join([
        r"\documentclass[11pt]{article}",
        r"\usepackage[T1]{fontenc}", r"\usepackage{lmodern}", r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{amsmath}",
        r"\usepackage[colorlinks=true,urlcolor=blue,linkcolor=blue,citecolor=blue]{hyperref}",
        r"\setlength{\parindent}{0pt}", r"\setlength{\parskip}{0.6em}",
        r"\emergencystretch=3em",
        r"\hypersetup{pdftitle={" + escape(meta["title"]) + "}, pdfauthor={" + escape(meta["author"])
        + "}, pdfkeywords={" + escape(keywords) + "}}",
        r"\title{" + escape(meta["title"]) + "}",
        r"\author{" + escape(meta["author"])
        + (r"\thanks{ORCID: \href{https://orcid.org/" + meta["orcid"] + "}{" + meta["orcid"] + "}}" if meta["orcid"] else "")
        + r" \\ \normalsize " + affiliation + (r" (\url{" + url.group(1) + "})" if url else "") + "}",
        r"\date{" + escape(meta["date"]) + "}",
    ])
    return (preamble + "\n\\begin{document}\n\\maketitle\n\n" + body + "\n\n"
            + "\\section*{References}\n\\small\n\\begin{enumerate}\n" + refs + "\n\\end{enumerate}\n\\end{document}\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--paper", default=str(HERE / "paper.md"))
    ap.add_argument("--bib", default=str(HERE / "paper.bib"))
    ap.add_argument("--out", default=str(HERE / "paper.tex"))
    ap.add_argument("--pdf", action="store_true", help="also run xelatex twice next to the .tex file")
    args = ap.parse_args(argv)
    tex = render(Path(args.paper).read_text(encoding="utf-8"), Path(args.bib).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.write_text(tex, encoding="utf-8")
    print(f"wrote {out} ({len(tex)} bytes)")
    if args.pdf:
        xelatex = shutil.which("xelatex") or "/Library/TeX/texbin/xelatex"
        for _ in range(2):
            proc = subprocess.run([xelatex, "-interaction=nonstopmode", "-halt-on-error", out.name],
                                  cwd=str(out.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode != 0:
                print(proc.stdout.decode("utf-8", "replace")[-2000:])
                return 1
        print(f"wrote {out.with_suffix('.pdf')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
