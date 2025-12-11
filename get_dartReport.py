from config import API_KEY
import re, zipfile, requests
from io import BytesIO
from bs4 import BeautifulSoup


def unpack(rcept_no):
    url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={API_KEY}&rcept_no={rcept_no}"
    response = requests.get(url)
    results = []
    with zipfile.ZipFile(BytesIO(response.content)) as zf:
        for name in zf.namelist():
            with zf.open(name) as f:
                data = f.read()
                try: results.append(data.decode("utf-8"))
                except UnicodeDecodeError:
                    try: results.append(data.decode("cp949"))
                    except UnicodeDecodeError: print(f"Failed to decode: {name}")
    return results

def parse_table(table):
    rows, pending = [], {}

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
                if rowspan > 1:
                    pending[col_idx + i] = [rowspan - 1, text]
            col_idx += colspan
        consume_pending()
        if row_cells: rows.append(row_cells)

    return rows

def preprocess_with_tables(raw):
    soup = BeautifulSoup(raw, "html.parser")

    tables = []
    for idx, table in enumerate(soup.find_all("table")):
        placeholder = f"__TABLE_{idx}__"
        tables.append({"placeholder": placeholder, "rows": parse_table(table)})
        table.replace_with(f"\n{placeholder}\n")

    text = soup.get_text(separator="\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip(), tables

def split_by_title(raw):
    matches = list(re.compile(r"<TITLE[^>]*>(.*?)</TITLE>", re.I | re.S).finditer(raw))
    segments = {}

    for idx, match in enumerate(matches):
        title_html = match.group(1)
        title = BeautifulSoup(title_html, "html.parser").get_text(" ", strip=True) or f"TITLE_{idx+1}"

        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw)
        body_text, body_tables = preprocess_with_tables(raw[start:end])
        segments[title] = {"text": body_text, "tables": body_tables}
        
    return segments




if __name__ == "__main__":
    rcept_no = "20251210000274"
    texts = unpack(rcept_no)[0]
    sections = split_by_title(texts)

    restricted_titles = ["주요사항보고서", "정정신고"]
    filtered_sections = {}
    for title, content in sections.items():
        simple_title = title.replace(" ", "")
        if any(restricted_title in simple_title for restricted_title in restricted_titles):
            continue
        filtered_sections[title] = content

    for title, content in filtered_sections.items():
        print(f"*********************************{title}*********************************")
        print(content)
        print("*********************************END*********************************")
        print("\n")

