from config import API_KEY

import re
import zipfile
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def unpack(rcept_no: str) -> list:
    '''
    input: rcept_no
    output: list of texts in the report (full text for each file in the archive)
    '''
    source_download_url = "https://opendart.fss.or.kr/api/document.xml"
    url = f"{source_download_url}?crtfc_key={API_KEY}&rcept_no={rcept_no}"
    response = requests.get(url)
    
    all_texts = []
    try:
        with zipfile.ZipFile(BytesIO(response.content)) as zf:
            for name in zf.namelist():
                with zf.open(name) as f:
                    data = f.read()
                    try: text = data.decode('utf-8')
                    except UnicodeDecodeError:
                        try: text = data.decode('cp949')
                        except UnicodeDecodeError: 
                            print(f"Failed to decode: {name}")
                            text = None
                    if text is not None: all_texts.append(text)
    except zipfile.BadZipFile: pass
    return all_texts

def split_by_title(raw: str) -> dict:
    title_pattern = re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.IGNORECASE | re.DOTALL)
    matches = list(title_pattern.finditer(raw))
    segments = {}

    for idx, match in enumerate(matches):
        title_html = match.group(1)
        title = BeautifulSoup(title_html, "html.parser").get_text(" ", strip=True)
        if not title:
            title = f"TITLE_{idx+1}"

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        body_raw = raw[start:end]
        body_clean = preprocess_text(body_raw)
        segments[title] = body_clean
        
    return segments

def table_to_text(table, separator: str = " | ") -> str:
    rows = []
    pending = {}

    for tr in table.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if not cells and not pending: continue

        row_cells = []
        col_idx = 0

        def consume_pending():
            nonlocal col_idx
            while col_idx in pending:
                span_rows, text = pending[col_idx]
                row_cells.append(text)
                span_rows -= 1
                if span_rows <= 0: pending.pop(col_idx)
                else: pending[col_idx][0] = span_rows
                col_idx += 1

        for cell in cells:
            consume_pending()
            text = cell.get_text(" ", strip=True)
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)

            for i in range(colspan):
                row_cells.append(text)
                if rowspan > 1: pending[col_idx + i] = [rowspan - 1, text]
            col_idx += colspan
        consume_pending()
        if row_cells: rows.append(separator.join(row_cells))

    return "\n".join(rows)


def preprocess_text(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")

    # Convert tables to text blocks before full extraction to retain structure
    for table in soup.find_all("table"):
        table_text = table_to_text(table)
        table.replace_with(f"\n{table_text}\n")

    text = soup.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

def parse_by_title(text: str) -> dict:
    pattern = r"(^|\n)(TITLE[^\n]*)"
    parts = re.split(pattern, text, flags=re.IGNORECASE)
    segments = {}
    current_title = None
    content = []
    for part in parts:
        if part is None or part.strip() == "":
            continue
        if part.strip().upper().startswith("TITLE"):
            if current_title and content:
                segments[current_title] = "".join(content).strip()
            current_title = part.strip()
            content = []
        else:
            content.append(part)
    if current_title and content:
        segments[current_title] = "".join(content).strip()
    return segments





if __name__ == "__main__":
    rcept_no = "20251210000274"
    texts = unpack(rcept_no)
    print(texts)

    # output_dir = Path("dart_outputs")
    # output_dir.mkdir(exist_ok=True)

    # for idx, text in enumerate(texts, start=1):
    #     cleaned = preprocess_text(text)
    #     cleaned_path = output_dir / f"{rcept_no}_part{idx}.txt"
    #     cleaned_path.write_text(cleaned, encoding="utf-8")

    #     sections = parse_by_title(cleaned)
    #     sections_path = output_dir / f"{rcept_no}_part{idx}_sections.txt"
    #     with sections_path.open("w", encoding="utf-8") as f:
    #         for title, content in sections.items():
    #             f.write(f"[{title}]\n{content}\n\n")

    #     print(f"Wrote {cleaned_path} ({len(cleaned)} chars)")
    #     print(f"Wrote {sections_path} ({len(sections)} sections)")