#!/usr/bin/env python3
"""掃描本專案所有 html 檔案內的 href/src，確認目標檔案存在、無死鏈。

用法（在 stage2-multipage/ 目錄下執行）：
    python3 check-links.py

規則：
- partials/header.html、partials/footer.html 是被 fetch 注入到「根目錄各頁面」的，
  瀏覽器會把裡面的相對路徑相對於「注入後所在頁面」（也就是網站根目錄）解析，
  不是相對於 partials/ 這個資料夾本身。所以這兩個檔案的連結也用根目錄當基準路徑檢查。
  完整說明見 docs/ARCHITECTURE.md。
- 忽略外部連結（http/https）、mailto:、tel:、javascript:、純錨點 (#xxx)。
- 錨點路徑（file.html#section）只檢查檔案本身是否存在，不驗證錨點 id 是否存在。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

ATTR_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"')

SKIP_PREFIXES = ("http://", "https://", "mailto:", "tel:", "javascript:", "//")


def find_html_files():
    files = []
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        if "node_modules" in dirpath or ".venv" in dirpath:
            continue
        for fn in filenames:
            if fn.endswith(".html"):
                files.append(os.path.join(dirpath, fn))
    return sorted(files)


def main():
    html_files = find_html_files()
    total_links = 0
    dead_links = []

    for path in html_files:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        for match in ATTR_RE.finditer(content):
            raw = match.group(1)
            if raw.startswith("#"):
                continue
            if raw.startswith(SKIP_PREFIXES):
                continue

            total_links += 1
            target = raw.split("#")[0].split("?")[0]
            if not target:
                continue

            resolved = os.path.normpath(os.path.join(ROOT, target))

            if not os.path.isfile(resolved):
                dead_links.append((path, raw, resolved))

    rel_html_files = [os.path.relpath(p, ROOT) for p in html_files]
    print("掃描的 html 檔案（%d 個）：%s" % (len(html_files), ", ".join(rel_html_files)))
    print("檢查 %d 條連結、%d 死鏈" % (total_links, len(dead_links)))
    if dead_links:
        print("死鏈明細：")
        for src_file, raw, resolved in dead_links:
            print("  %s 內的 %r -> 找不到 %s" % (os.path.relpath(src_file, ROOT), raw, resolved))
        sys.exit(1)
    else:
        print("全部連結都指向存在的檔案。")


if __name__ == "__main__":
    main()
