import pywikibot

# 站点
site = pywikibot.Site('en', 'xyy')
site.login()  # Must use account password; bot password does not work

rating_to = "GR"  # 两字母评级 codename (UR/ST/UF/FN/CD/LS/GR)
reason = "Batch rating gallery articles"  # 统一理由

# 读取页面列表
with open("pages_to_rate.txt", "r", encoding="utf-8") as f:
    pages = [line.strip() for line in f if line.strip()]

# 获取 CSRF token
token = site.tokens['csrf']

for title in pages:
    params = {
        'action': 'change-rating',
        'format': 'json',
        'title': title,
        'rating-to': rating_to,
        'reason': reason,
        'token': token
    }
    try:
        result = site._simple_request(**params).submit()
        print(f"Rated {title} -> {rating_to}: {result}")
    except Exception as e:
        print(f"Failed to rate {title}: {e}")
