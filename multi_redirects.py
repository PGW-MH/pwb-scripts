import csv
import pywikibot

site = pywikibot.Site('en', 'xyy')
site.login()

csv_file = 'pages_to_redirect.csv'


def create_redirects_from_csv(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)

        for row in reader:
            if len(row) >= 2:
                source_title = row[0].strip()
                target_title = row[1].strip()

                if not source_title or not target_title:
                    continue

                try:

                    source_page = pywikibot.Page(site, source_title)

                    if source_page.exists():
                        print(f"Page '{source_title}' already exists. Skipping...")
                        continue

                    redirect_content = f"#REDIRECT [[{target_title}]]"

                    source_page.text = redirect_content
                    source_page.save(summary=f"Creating redirect to [[{target_title}]]")
                    print(f"Created redirect: {source_title} -> {target_title}")

                except Exception as e:
                    print(f"Error creating redirect for {source_title} -> {target_title}: {e}")


create_redirects_from_csv(csv_file)
