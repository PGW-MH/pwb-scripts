import csv
import json
import re
from collections import defaultdict

import pywikibot
import requests


WIKI_FAMILY = "xyy"
WIKI_LANG = "en"
CSV_PATH = "still_episode.csv"

# 识别不到时使用这个
DEFAULT_SEASON_NAME = 'Martial World Rescue'  # e.g., "Explore Wolffy’s Mind"

EDIT_SUMMARY = "Moved stills to episode gallery. Powered by WeslieSearch-Vision (https://tuxiaobei-wesliesearch-vision.ms.show)"

API_BASE = "https://xyy.miraheze.org/w/api.php"
HEADERS = {"User-Agent": "Mozilla/5.0"}

GALLERY_HEADER_RE = re.compile(r'(?im)^==\s*Gallery\s*==\s*$')
WATCH_HEADER_RE = re.compile(r'(?im)^==\s*Watch\s*==\s*$')
NEXT_LEVEL2_HEADER_RE = re.compile(r'(?im)^==[^=\n].*?==\s*$')
GALLERY_BLOCK_RE = re.compile(r'(?is)<gallery>(.*?)</gallery>')
FILE_LINE_RE = re.compile(r'(?im)^\s*(File:[^\n]+?)\s*$')


def normalize_file_title(s: str) -> str:
    s = s.strip()
    if not s.lower().startswith("file:"):
        s = "File:" + s
    return s


def detect_season_name_from_first_row(first_row):
    """
    规则：
    - 第一行形如:
      File:Explore Wolffy’s Mind still 1.jpg,1
      那么提取 File: 和 still 之间的部分，得到 Explore Wolffy’s Mind
    - 如果识别不到，用 DEFAULT_SEASON_NAME
    """
    if not first_row or len(first_row) < 1:
        return DEFAULT_SEASON_NAME

    cell = first_row[0].strip()
    m = re.search(r'^File:(.+?)\s+still\b', cell, re.IGNORECASE)
    if m:
        season_name = m.group(1).strip()
        if season_name:
            return season_name

    return DEFAULT_SEASON_NAME


def read_csv(csv_path: str):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        raise ValueError("CSV is empty.")

    season_name = detect_season_name_from_first_row(rows[0])
    if not season_name:
        raise ValueError(
            "Cannot detect season name from first CSV row, and DEFAULT_SEASON_NAME is not set."
        )

    ep_to_files = defaultdict(list)

    # 第一行也要参与归类；它既包含文件名也包含集数
    for row in rows:
        if len(row) < 2:
            continue
        file_title = normalize_file_title(row[0])
        ep_raw = row[1].strip()
        if not ep_raw:
            continue
        try:
            ep_num = int(ep_raw)
        except ValueError:
            continue
        if file_title not in ep_to_files[ep_num]:
            ep_to_files[ep_num].append(file_title)

    return season_name, ep_to_files


def fetch_json_data(season_name: str):
    params = {
        "action": "parse",
        "page": f"Template:Episode/{season_name.replace(' ', '_')}.json",
        "prop": "wikitext",
        "formatversion": "2",
        "format": "json",
        "origin": "*"
    }
    response = requests.get(API_BASE, params=params, headers=HEADERS, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "parse" not in data or "wikitext" not in data["parse"]:
        raise RuntimeError(f"Unexpected API response: {data}")

    return json.loads(data["parse"]["wikitext"])


def get_episode_list(json_data):
    if not isinstance(json_data, dict) or "episodes" not in json_data:
        raise ValueError("JSON data does not contain 'episodes'.")
    if not isinstance(json_data["episodes"], list):
        raise ValueError("'episodes' is not a list.")
    return json_data["episodes"]


def episode_num(entry):
    try:
        return int(entry["num"])
    except Exception:
        return None


def episode_page_title(entry):
    title = entry["english"]
    if "suffix" in entry:
        title += f" ({entry['suffix']})"
    return title


def merge_into_gallery(text: str, file_titles: list[str]) -> tuple[str, bool]:
    if not file_titles:
        return text, False

    old_text = text or ""
    existing_files = {m.group(1).strip() for m in FILE_LINE_RE.finditer(old_text)}
    to_add = [f for f in file_titles if f not in existing_files]
    if not to_add:
        return old_text, False

    gallery_match = GALLERY_HEADER_RE.search(old_text)
    if gallery_match:
        sec_start = gallery_match.end()
        next_header = NEXT_LEVEL2_HEADER_RE.search(old_text, pos=sec_start)
        sec_end = next_header.start() if next_header else len(old_text)

        section = old_text[sec_start:sec_end]
        block_match = GALLERY_BLOCK_RE.search(section)

        if block_match:
            inner = block_match.group(1)
            inner_lines = [ln.strip() for ln in inner.splitlines() if ln.strip()]
            inner_set = set(inner_lines)

            real_add = [f for f in to_add if f not in inner_set]
            if not real_add:
                return old_text, False

            insertion = "\n".join(real_add)
            if inner.strip():
                new_inner = inner.rstrip() + "\n" + insertion + "\n"
            else:
                new_inner = "\n" + insertion + "\n"

            new_section = (
                section[:block_match.start(1)]
                + new_inner
                + section[block_match.end(1):]
            )
            new_text = old_text[:sec_start] + new_section + old_text[sec_end:]
            return new_text, new_text != old_text

        gallery_block = "<gallery>\n" + "\n".join(to_add) + "\n</gallery>\n"
        prefix = old_text[:sec_end]
        suffix = old_text[sec_end:]
        if prefix and not prefix.endswith("\n"):
            prefix += "\n"
        new_text = prefix + gallery_block + suffix
        return new_text, new_text != old_text

    watch_match = WATCH_HEADER_RE.search(old_text)
    insert_pos = watch_match.start() if watch_match else len(old_text)

    gallery_section = (
        "==Gallery==\n"
        "<gallery>\n"
        + "\n".join(to_add)
        + "\n</gallery>\n"
    )

    before = old_text[:insert_pos]
    after = old_text[insert_pos:]

    if before and not before.endswith("\n"):
        before += "\n"
    if after and not after.startswith("\n"):
        gallery_section += "\n"

    new_text = before + gallery_section + after
    return new_text, new_text != old_text


def main():
    site = pywikibot.Site(WIKI_LANG, WIKI_FAMILY)
    site.login()

    season_name, ep_to_files = read_csv(CSV_PATH)
    print("Season name:", season_name)
    print("CSV episodes:", sorted(ep_to_files.keys()))

    json_data = fetch_json_data(season_name)
    episodes = get_episode_list(json_data)

    ep_to_titles = defaultdict(list)
    for ep in episodes:
        n = episode_num(ep)
        if n is None:
            continue
        title = episode_page_title(ep)
        if title not in ep_to_titles[n]:
            ep_to_titles[n].append(title)

    for ep_num in sorted(ep_to_files.keys()):
        if ep_num not in ep_to_titles:
            print(f"[Skip] episode {ep_num}: not found in JSON.")
            continue

        files = ep_to_files[ep_num]

        for page_title in ep_to_titles[ep_num]:
            page = pywikibot.Page(site, page_title)
            if not page.exists():
                print(f"[Skip] {page_title}: page does not exist.")
                continue

            old_text = page.text or ""
            new_text, changed = merge_into_gallery(old_text, files)

            if not changed:
                print(f"[No change] {page_title}")
                continue

            # page.text = new_text
            # page.save(summary=EDIT_SUMMARY)
            # print(f"[Saved] {page_title}: added {len(files)} files for episode {ep_num}")
            import difflib

            def show_diff(old_text: str, new_text: str, title: str):
                old_lines = (old_text or "").splitlines()
                new_lines = (new_text or "").splitlines()

                diff = difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"{title} (old)",
                    tofile=f"{title} (new)",
                    lineterm=""
                )

                print("\n".join(diff))

            # ===== diff + 首次确认机制 =====
            if not hasattr(main, "_confirmed"):
                print("\n================ DIFF PREVIEW ================")
                show_diff(old_text, new_text, page_title)
                print("=============================================\n")

                ans = input("Apply this and all subsequent edits? (y/N): ").strip().lower()
                if ans != "y":
                    print("Aborted by user.")
                    return

                main._confirmed = True
            # ============================================

            page.text = new_text
            page.save(summary=EDIT_SUMMARY)
            print(f"[Saved] {page_title}: added {len(files)} files for episode {ep_num}")


if __name__ == "__main__":
    main()
