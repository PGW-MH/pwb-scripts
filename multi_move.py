import csv
import pywikibot
from pywikibot import page

site = pywikibot.Site('en', 'xyy')
site.login()

no_redirect = True
csv_file = 'pages_to_move.csv'


def move_pages_from_csv(csv_file, no_redirect=False):
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)

        for row in reader:
            if len(row) >= 2:
                old_page_title = row[0].strip()
                new_page_title = row[1].strip()

                if not old_page_title or not new_page_title:
                    continue

                try:
                    old_page = pywikibot.Page(site, old_page_title)
                    print(f"Moving page: {old_page_title} -> {new_page_title}")
                    old_page.move(new_page_title, reason="Batch move from CSV", noredirect=no_redirect)

                except Exception as e:
                    print(f"Error moving {old_page_title} to {new_page_title}: {e}")


move_pages_from_csv(csv_file, no_redirect)
