"""
从交集分类中遍历 File 页面，取文件真实 URL（通过 API），下载到临时文件，
调用 Gradio /submit 获取 season/episode，替换/插入 Summary 段为:
    {{fi|s={{ep|SEASON|EP}}}}
"""
import argparse
import os
import re
import tempfile
import time
import traceback
import pywikibot
import requests
from gradio_client import Client, handle_file

# ------------------ 配置 ------------------
WIKI_FAMILY = "xyy"
WIKI_LANG = "en"
API_BASE = "https://xyy.miraheze.org/w/api.php"

CAT_A = "Category:Files_missing_source"
CAT_B = "Category:Donghua_screenshots"

GRADIO_URL = "https://tuxiaobei-wesliesearch-vision.ms.show/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://xyy.miraheze.org/"
}
# -----------------------------------------

client = Client(GRADIO_URL)

# 匹配 header 的正则（用于查找 Summary 段）
SUMMARY_HEADER_RE = re.compile(r'^(?P<header>={2,}\s*Summary\s*={2,})', re.IGNORECASE | re.MULTILINE)
NEXT_HEADER_RE = re.compile(r'^(={2,}.*?={2,})', re.MULTILINE)

def get_file_url_via_api(filename: str) -> str | None:
    """
    使用 MediaWiki API 获取文件真实 URL（imageinfo -> url）。
    filename 应为不带前缀的文件名，例如 '0-1.png'。
    返回 URL 或 None。
    """
    params = {
        "action": "query",
        "prop": "imageinfo",
        "titles": f"File:{filename}",
        "iiprop": "url",
        "format": "json"
    }
    try:
        r = requests.get(API_BASE, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        j = r.json()
        pages = j.get("query", {}).get("pages", {})
        for pid, pdata in pages.items():
            if "imageinfo" in pdata:
                return pdata["imageinfo"][0].get("url")
    except Exception as e:
        print("  [API error] get_file_url_via_api:", e)
    return None

def parse_top_season_episode(result_tuple):
    """
    从 gradio 返回的 tuple 解析第一条（前 6 项）。
    返回 (season_code, episode_number) 或 (None, None)。
    season_code 尽量保留类似 'TV23' 的短代号；episode_number 只保留数字字符串。
    """
    try:
        if not result_tuple or len(result_tuple) < 2:
            return None, None
        season_raw = result_tuple[0] or ""
        ep_raw = result_tuple[1] or ""
        # season: 取第一段（遇到中/英文冒号或空格即切分），只保留字母数字下划线等
        s = re.split(r'[：:\s]', str(season_raw).strip())[0]
        m = re.match(r'([A-Za-z0-9_+-]+)', s)
        season_code = m.group(1) if m else s

        # episode: 找第一个数字
        em = re.search(r'(\d+)', str(ep_raw))
        ep_num = em.group(1) if em else None

        return season_code, ep_num
    except Exception as e:
        print(" parse_top_season_episode error:", e)
        return None, None

def replace_or_insert_summary_simple(text: str, new_content: str) -> (str, bool):
    """
    将页面 text 的 Summary 段替换为 new_content（不含 header），
    如果没有 Summary 段则插入到文首（在第一个 header 之前）。
    返回 (new_text, changed_bool).
    new_content 传入应为最终段内文本（例如 "{{fi|s={{ep|TV23|51}}}}"）
    """
    if text is None:
        text = ""

    # search for Summary header
    m = SUMMARY_HEADER_RE.search(text)
    if m:
        # header starts at m.start(); find end of this section (next header after m.end())
        start_of_section = m.end()
        # find next header after start_of_section
        next_m = NEXT_HEADER_RE.search(text, pos=start_of_section)
        end_of_section = next_m.start() if next_m else len(text)
        # build new text
        new_text = text[:m.end()] + "\n" + new_content.strip() + "\n" + text[end_of_section:]
        changed = not (new_text.strip() == text.strip())
        return new_text, changed
    else:
        # no Summary header: insert at top before first header if any, else prepend
        first_header = NEXT_HEADER_RE.search(text)
        if first_header:
            insert_pos = first_header.start()
            new_text = text[:insert_pos] + "== Summary ==\n" + new_content.strip() + "\n\n" + text[insert_pos:]
        else:
            # no headers at all
            new_text = "== Summary ==\n" + new_content.strip() + "\n\n" + text
        changed = not (new_text.strip() == text.strip())
        return new_text, changed

def process_intersection(auto_apply=False, limit=None):
    site = pywikibot.Site(WIKI_LANG, WIKI_FAMILY)
    site.login()

    cat_a = pywikibot.Category(site, CAT_A)
    cat_b = pywikibot.Category(site, CAT_B)

    members_a = {p.title() for p in cat_a.members(namespaces=6)}
    members_b = {p.title() for p in cat_b.members(namespaces=6)}
    intersection = sorted(members_a & members_b)

    print(f"Found {len(intersection)} file pages in intersection.")
    if limit:
        intersection = intersection[:limit]

    for title in intersection:
        try:
            print("\n---\nProcessing:", title)
            page = pywikibot.Page(site, title)
            if not page.exists():
                print(" Page does not exist; skip.")
                continue

            # extract filename
            if title.lower().startswith("file:"):
                filename = title.split(":", 1)[1]
            else:
                print(" Not a file page; skip.")
                continue

            # get canonical file url from API
            file_url = get_file_url_via_api(filename)
            if not file_url:
                print("  Could not get remote file URL via API; skip.")
                continue
            print("  file URL:", file_url)

            # download to temporary file
            try:
                resp = requests.get(file_url, headers=HEADERS, stream=True, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                print("  download failed:", e)
                continue

            fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1] or ".png")
            os.close(fd)
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # call gradio
            try:
                result = client.predict(
                    img=handle_file(tmp_path),
                    query_num=1,
                    season_filter="",
                    api_name="/submit"
                )
            except Exception as e:
                print("  Gradio call failed:", e)
                # cleanup tmp
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                continue

            season_code, ep_num = parse_top_season_episode(result)
            if not season_code or not ep_num:
                print("  cannot parse season/episode from result; sample:", result[:12])
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                continue

            print(f"  Parsed: season={season_code}, episode={ep_num}")

            new_inner = "{{fi|s={{ep|" + season_code + "|" + ep_num + "}}|sflag=WeslieSearch-Vision}}"
            old_text = page.text or ""
            new_text, changed = replace_or_insert_summary_simple(old_text, new_inner)
            if not changed:
                print("  No change needed.")
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                continue

            # preview + prompt (unless auto_apply)
            if not auto_apply:
                print("  Preview (first 200 lines):")
                print("\n".join(new_text.splitlines()[:200]))
                ans = input(" Apply this edit? (y/N): ").strip().lower()
                if ans != "y":
                    print("  skipped by user.")
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue

            # save page
            try:
                page.text = new_text
                page.save(summary="autofix file source with WeslieSearch-Vision (https://tuxiaobei-wesliesearch-vision.ms.show)")
                print("  Saved.")
            except Exception as e:
                print("  Save failed:", e)
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

            # small delay to be polite
            time.sleep(1.0)

        except Exception as e:
            print(" ERROR processing", title, ":", e)
            traceback.print_exc()
            input("Press Enter to continue...")

def main():
    parser = argparse.ArgumentParser(description="Update file pages from Gradio results")
    parser.add_argument("--yes", action="store_true", help="Auto apply edits without prompting")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of pages")
    args = parser.parse_args()

    process_intersection(auto_apply=args.yes, limit=args.limit)

if __name__ == "__main__":
    main()
