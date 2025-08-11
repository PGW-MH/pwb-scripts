import pywikibot

def release_date_to_ym(release_date: str) -> str:
    # release_date 格式假设为 "April 2025"
    month_map = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12"
    }
    parts = release_date.split()
    if len(parts) == 2:
        month, year = parts
        month_num = month_map.get(month, "00")
        return f"{year}{month_num}"
    else:
        # 如果格式不对，直接返回空或者默认值
        return "000000"

def check_page_exists(site, title):
    page = pywikibot.Page(site, title)
    return page.exists()

def create_card_page_content(card_number, rarity, release_date, obtained_text):
    # 格式化卡牌编号，3位数，前导0
    card_num_str = f"{card_number:03d}"
    # 模板中的日期格式 yyyyMM 例如 202504
    # release_ym = release_date.replace(" ", "")  # 简单去空格
    # release_ym = release_ym[:4] + release_ym[4:6]  # 简单处理为202504（假设格式是“April 2025”）
    # 这里你可以根据需要改成更严谨的格式转换
    release_ym = release_date_to_ym(release_date)

    # 生成模板内容
    content = f"""{{{{Card
|front=XYY-{rarity}-{card_num_str}-{release_ym}.jpg
|back=XYY-{rarity}-back-{release_ym}.jpg
|character=
|text=
|distributor=Auldey
|release={release_date}
|obtained={obtained_text}
}}}}"""
    return content

def main():
    site = pywikibot.Site('en', 'xyy')
    site.login()

    rarity = "UC"  # 稀有度
    release_date = "April 2025"  # 发行时间，保持和模板中一致的格式
    obtained_text = "[[Friendship Card Friendship Pack Vol. 3]]"  # 获取途径

    start_num = 1
    end_num = 2

    for num in range(start_num, end_num + 1):
        page_title = f"Card:XYY-{rarity}-{num:03d} (Auldey {release_date})"
        if check_page_exists(site, page_title):
            print(f"Page '{page_title}' already exists, skipping.")
        else:
            print(f"Creating page '{page_title}'...")
            content = create_card_page_content(num, rarity, release_date, obtained_text)
            page = pywikibot.Page(site, page_title)
            page.text = content
            page.save(summary=f"Creating card page for {page_title}")

if __name__ == "__main__":
    main()
