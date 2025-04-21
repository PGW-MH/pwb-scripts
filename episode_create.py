import pywikibot
import requests
import re


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
    url = f'https://xyy.fandom.com/wiki/Template:Episode/{season_name.replace(" ", "_")}.json?action=raw'
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to fetch JSON data from {url}")


def check_page_exists(site, title):
    page = pywikibot.Page(site, title)
    return page.exists()


def create_page_content(season_abbr, season_name, episode):
    ordinal_num = to_ordinal(episode['num'])
    english_title = episode['english']
    chinese_title = episode['chinese']
    pinyin_title = episode['pinyin']

    page_content = f"""{{{{Stub}}}}"""

    if add_conjectural:
        page_content += f"{{{{Conjectural}}}}"

    page_content += f"""
{{{{Infobox episode|{season_abbr}|{episode['num']}|image={season_abbr}{episode['num']:02d}.png}}}}
{{{{zhongwen|“{english_title}”|{chinese_title}|{pinyin_title}}}}} is the {ordinal_num} episode of ''[[{season_name}]]''.

==Characters present==
{{{{TBA}}}}

==Summary==
{{{{TBA}}}}
"""
    if add_watch:
        page_content += f"""
==Watch==
[[File:{re.sub(r':.*', '', re.sub(r'[,!]', '', season_name))} EP{episode['num']:02d}]]
"""
    page_content += f"""
==Navigation==
{{{{{season_abbr}|uncollapsed}}}}
{{{{zh|{chinese_title}}}}}
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
add_conjectural = input("Do you want to add {{Conjectural}} template? (yes/no): ").strip().lower() == 'yes'
add_watch = input("Do you want to add the Watch section? (yes/no): ").strip().lower() == 'yes'

process_season(season_name, season_abbr, add_conjectural, add_watch)
