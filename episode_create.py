import pywikibot
import requests
import re
import json
import os
from urllib.parse import urlparse, parse_qs


local_json_data = None


def to_ordinal(n):
    ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
    firsts = ['', 'first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth']
    teens = ['tenth', 'eleventh', 'twelfth', 'thirteenth', 'fourteenth', 'fifteenth', 'sixteenth', 'seventeenth', 'eighteenth', 'nineteenth']
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
    tenths = ['', '', 'twentieth', 'thirtieth', 'fortieth', 'fiftieth', 'sixtieth', 'seventieth', 'eightieth', 'ninetieth']

    res = ''
    if n >= 100:
        res += ones[n // 100] + ' hundred'
        n %= 100
    if n == 0:
        res += 'th'
        return res
    else:
        res += ' and ' if res else ''
    if n >= 20:
        if n % 10 == 0:
            res += tenths[n // 10]
        else:
            res += tens[n // 10] + '-' + firsts[n % 10]
    elif n >= 10:
        res += teens[n - 10]
    else:
        res += firsts[n]
    return res


def fetch_json_data(season_name):
    api_url = "https://xyy.miraheze.org/w/api.php"
    params = {
        "action": "parse",
        "page": f"Template:Episode/{season_name.replace(' ', '_')}.json",
        "prop": "wikitext",
        "formatversion": "2",
        "format": "json",
        "origin": "*"
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    response = requests.get(api_url, params=params, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if "parse" in data and "wikitext" in data["parse"]:
            return json.loads(data["parse"]["wikitext"])
        else:
            raise Exception(f"Unexpected API response: {data}")
    else:
        raise Exception(f"Failed to fetch JSON data: {response.status_code}")


def check_page_exists(site, title):
    page = pywikibot.Page(site, title)
    return page.exists()


def extract_youtube_id(url):
    try:
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        if "youtube.com/watch" in url:
            query = parse_qs(urlparse(url).query)
            return query.get("v", [None])[0]
    except Exception:
        return None
    return None


def create_page_content(season_abbr, season_name, episode):
    global local_json_data

    ordinal_num = to_ordinal(episode['num'])
    english_title = episode['english']
    chinese_title = episode['chinese']
    pinyin_title = episode['pinyin']

    zh_page_name = chinese_title
    summary_en = None
    yt_id = None

    if local_json_data:
        for ep in local_json_data:
            if ep.get("集数") == episode['num']:
                if ep.get("页面名"):
                    zh_page_name = ep["页面名"]
                if ep.get("剧情简介（YouTube英文）"):
                    summary_en = ep["剧情简介（YouTube英文）"]
                if ep.get("链接（YouTube中文）"):
                    yt_id = extract_youtube_id(ep["链接（YouTube中文）"])
                break

    page_content = ''

    if add_conjectural:
        page_content += f"{{{{Conjectural}}}}\n"

    page_content += f"""{{{{Infobox episode|{season_abbr}|{episode['num']}|image={season_abbr}{episode['num']:02d}.png}}}}
{{{{EpisodeZ}}}} is the {ordinal_num} episode of [[{season_name}]].
"""

    if summary_en:
        page_content += f"\n{summary_en}\n"

    page_content += """
==Characters present==
{{clist}}

==Summary==
{{TBA}}
"""

    if add_watch:
        page_content += "\n==Watch==\n"
        if yt_id:
            page_content += f"{{{{yt|{yt_id}}}}}\n"
        else:
            page_content += "{{yt|}}\n"

    page_content += f"""
==Navigation==
{{{{{season_abbr[:-1] if season_abbr[-1].isdigit() else season_abbr}|uncollapsed}}}}
[[zh:{zh_page_name}]]
"""

    return page_content


def process_season(season_name, season_abbr, add_conjectural, add_watch):
    try:
        data = fetch_json_data(season_name)
    except Exception as e:
        print(f"Error fetching JSON data: {e}")
        return

    site = pywikibot.Site('en', 'xyy')
    site.login()

    for episode in data['episodes']:
        episode_title = episode['english']
        if 'suffix' in episode:
            episode_title += f" ({episode['suffix']})"

        if check_page_exists(site, episode_title):
            print(f"Page '{episode_title}' already exists.")
        else:
            print(f"Creating page for '{episode_title}'...")
            page_content = create_page_content(season_abbr, season_name, episode)
            page = pywikibot.Page(site, episode_title)
            page.text = page_content
            page.save(summary=f"Creating episode page for {episode_title}")


season_name = input("Enter the season name (e.g., Marching to the New Wonderland): ")
season_abbr = input("Enter the season abbreviation (e.g., MttNW): ")
add_conjectural = input("Do you want to add {{Conjectural}} template? (y/n): ").strip().lower() == 'y'
add_watch = input("Do you want to add the Watch section? (y/n): ").strip().lower() == 'y'
local_json_path = input("Do you have a PGP-exported JSON file for this season? (enter path or leave blank): ").strip()

if (local_json_path.startswith('"') and local_json_path.endswith('"')) or \
   (local_json_path.startswith("'") and local_json_path.endswith("'")):
    local_json_path = local_json_path[1:-1]

if local_json_path:
    local_json_path = os.path.expanduser(local_json_path)
    local_json_path = os.path.abspath(local_json_path)

if local_json_path:
    print(f"Trying to load local JSON from: {local_json_path}")
    if os.path.isfile(local_json_path):
        try:
            with open(local_json_path, "r", encoding='utf-8') as f:
                local_json_data = json.load(f)
            print(f"Loaded local JSON data from {local_json_path}")
        except Exception as e:
            print(f"Failed to parse local JSON file: {e}")
            local_json_data = None
    else:
        print("File not found:", local_json_path)
        local_json_data = None
else:
    local_json_data = None

process_season(season_name, season_abbr, add_conjectural, add_watch)
