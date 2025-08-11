import csv
import pywikibot

# 配置 pywikibot 站点，确保你在用户配置文件中正确设置站点
site = pywikibot.Site('en', 'xyy')
site.login()  # 使用配置的凭证登录

csv_file = 'pages_to_delete.txt'  # CSV 文件路径

def delete_pages_from_csv(csv_file, reason="Batch delete from CSV (delete to re-import)"):
    with open(csv_file, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)

        for row in reader:
            if not row:
                continue
            page_title = row[0].strip()

            if not page_title:
                continue

            try:
                page = pywikibot.Page(site, page_title)

                if page.exists():
                    print(f"Deleting page: {page_title}")
                    page.delete(reason=reason, prompt=False)
                else:
                    print(f"Page does not exist: {page_title}")

            except Exception as e:
                print(f"Error deleting {page_title}: {e}")

# 调用批量删除功能
delete_pages_from_csv(csv_file)
