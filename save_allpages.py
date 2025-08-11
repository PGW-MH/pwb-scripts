import pywikibot
import csv

# 指定站点
site = pywikibot.Site('en', 'xyy')
site.login()

# 要处理的名字空间
namespaces = [0]  # 例如 主空间=0, Talk=1, User=2

# 输出 CSV 文件
output_file = "pages_list.csv"

with open(output_file, "w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    # 写表头
    writer.writerow(["Page title"])

    for ns in namespaces:
        for page in site.allpages(namespace=ns):
            # if page.isRedirectPage():
            #     continue
            writer.writerow([page.title()])
            print(f"Wrote: {page.title()}")
            # try:
            #     title = page.title()
            #     length = len(page.text.encode("utf-8"))  # 字节数
            #     writer.writerow([title, length])
            #     print(f"Wrote: {title} ({length} bytes)")
            # except Exception as e:
            #     print(f"Error processing {page.title()}: {e}")

print(f"✅ 已保存到 {output_file}")
