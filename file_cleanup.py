import pywikibot
import re
import difflib
import html

site = pywikibot.Site('en', 'xyy')
site.login()

FILE_NS = 6  # File namespace

# 匹配 Summary / Licensing 标题（并保留原始标题字符串）
HEADER_REGEX = re.compile(r'^(?P<header>={2,}\s*(?P<title>.+?)\s*={2,})\s*$', re.MULTILINE|re.IGNORECASE)

# 允许的 licensing template 名称（小写比较）
ALLOWED_LICENSE_TEMPLATES = {
    'cc-by-sa-3.0', 'cc-by-sa-4.0',
    'fairuse', 'fairuse-photoscan', 'fairuse-screenshot', 'fairuse-webarchive',
    'from wikimedia', 'other free',
    'pd', 'pd-shape', 'pd-textlogo', 'pd-webarchive',
    'permission', 'self'
}
# 允许的 summary template base names
ALLOWED_SUMMARY_TEMPLATES = {'fi', 'file_information', 'file information'}

def get_url(title):
    return 'https://xyy.miraheze.org/wiki/' + title.replace(' ', '_')

def section_is_single_template_whole(section_text, allowed_templates):
    """
    判断一个 section（header 之后到下一 header 之前的整段文本）是否仅包含一个模板（允许多行）。
    返回 (True, template_name_lower) 或 (False, None)
    """
    if section_text is None:
        return False, None
    s = section_text.strip()
    if not s:
        return False, None
    # 必须以 {{ 开头并以 }} 结尾（允许跨多行）
    if not (s.startswith('{{') and s.endswith('}}')):
        return False, None
    name = get_template_name_from_line(s)
    if not name:
        return False, None
    return (name.lower() in allowed_templates), name.lower()

def extract_section_block_from_text(raw_text, section_title):
    """
    从 raw_text 中直接抽取指定标题（case-insensitive）的 section 内容（header 之后到下一 header 之前，不做 strip）。
    返回该段原始字符串（包含任何换行/空白），若找不到返回 None。
    """
    # 使用 HEADER_REGEX 原始匹配器查找 header 位置（和 split_headers 使用的正则相同）
    it = list(HEADER_REGEX.finditer(raw_text))
    for i, m in enumerate(it):
        title = m.group('title').strip().lower()
        if title == section_title.lower():
            start = m.end()
            # 下一 header 的 start 如果存在
            if i + 1 < len(it):
                end = it[i+1].start()
            else:
                end = len(raw_text)
            return raw_text[start:end]
    return None

def equal_ignoring_trailing_single_newline(a, b):
    """
    如果 a 与 b 完全相等，或 a == b + '\\n'，或 b == a + '\\n'，则返回 True。
    其它情况返回 False。
    """
    if a is None:
        a = ''
    if b is None:
        b = ''
    if a == b:
        return True
    if a.endswith('\n') and a[:-1] == b:
        return True
    if b.endswith('\n') and b[:-1] == a:
        return True
    return False


def split_headers(text):
    """
    返回 (leading_text, list_of_sections)
    每个 section 为 (header_full_text, title_normalized, start_index, end_index, content_text)
    """
    sections = []
    last_pos = 0  # 上一个 header 的 end()，用于切取 content
    for m in HEADER_REGEX.finditer(text):
        start = m.start()
        title = m.group('title').strip()
        header_full = m.group('header')  # 保留原始 header 格式

        if not sections:
            # 首个 header 之前的内容暂时不设置为 leading，这里只记录
            # leading 最终由下方的 first_header_match 确定，以保证一致性
            pass
        else:
            # 上一个 section 的 content 应该从 last_pos（上一个 header 的 end()）到当前 header 的 start()
            prev = sections[-1]
            # 使用 last_pos（而不是 prev[3]，prev[3] 可能为 None）
            sections[-1] = (prev[0], prev[1], prev[2], start, text[last_pos:start])

        sections.append((header_full, title, start, None, None))
        last_pos = m.end()

    if not sections:
        leading = text
        return leading, []
    else:
        # 最后一节 content 从 last_pos 到文本末尾
        header_full, title, start, _, _ = sections[-1]
        sections[-1] = (header_full, title, start, len(text), text[last_pos:])

        # leading as before: text before first header
        first_header_match = HEADER_REGEX.search(text)
        leading = text[:first_header_match.start()] if first_header_match else ''
        return leading, sections


def first_nonempty_line(s):
    for line in s.splitlines():
        if line.strip():
            return line
    return ''

def is_single_template_line(line):
    line = line.strip()
    return line.startswith('{{') and line.endswith('}}')

def get_template_name_from_line(line):
    """
    从一行模板文本中解析模板名（取最外层左大括号之后到第一个 | 或 } 的部分）
    返回小写模板名或 None
    """
    line = line.strip()
    m = re.match(r'^\{\{\s*([^\|\}\s]+)', line)
    if not m:
        return None
    return m.group(1).strip().lower()

def prompt_apply(title, old_text, new_text):
    # 显示简短 diff，提示 y/n
    print("\n=== PAGE ===", get_url(title))
    # show a small unified diff
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff = difflib.unified_diff(old_lines[:200], new_lines[:200], lineterm='')
    # print only first 40 diff lines to avoid太长
    printed = 0
    for i, line in enumerate(diff):
        if printed >= 60:
            break
        print(line)
        printed += 1
    print("...") if printed >= 60 else None
    while True:
        choice = input("Apply this edit? (y/n): ").strip().lower()
        if choice in ('y','n'):
            return choice == 'y'

def normalize_spaces_between_sections(original_between_text):
    """
    如果原来只有 0 或 1 个空行，保留原样（即返回 '' 或 '\\n' 或包含空格的那串）；
    如果有多于 1 个连续空行，则缩减为单个换行 '\\n'。
    如果 original_between_text 包含非空白字符（比如注释等），则保留原样。
    """
    if original_between_text is None:
        return '\n'

    # 只包含空白（空格/制表/换行）的情况
    if original_between_text.strip() == '':
        # count how many '\n' characters are present
        n_newlines = original_between_text.count('\n')

        # 没有换行（完全为空或只有空格） -> 保留原样（通常是 '')
        if n_newlines == 0:
            return original_between_text

        # 有 1 个换行或多于 1 个换行 -> 归一为单个 '\n'
        # （如果你想保留原来是 '\r\n'、' \n' 等微差，可改为 return original_between_text
        # 但为了稳定只返回 '\n' 更一致）
        return '\n'

    # 含有非空白字符（比如注释或文本），不做改动，完整保留
    return original_between_text

def parse_title(title):
    # 允许的 season 列表
    allowed_seasons = [
        's1', 'pgabbw', 'xyyyhtl', 'pgsg', 'yyydh', 'jos', 'yykldyn', 'sd', 'qsmxxyy', 'happy happy bang bang', 'hhbb', 'gkljy', 'tac', 'jjdlm', 'thd', 'kxrj', 'hf', 'kxfcs', 'ptac', 'lyyddc', 'dlw', 'yyxxy', "the tailor's closet", 'ttc', 'ycdmx', 'lyb', 'mmlfk', 'aitpw', 'yssjlxj', 'mttnw', 'xh1', 'xhcsj', 'tld', 'yyxzt', 'aits', 'shlxj', 'mttnw2', 'xh2', 'woi', 'fmdzz', 'flying island', 'fitsa', 'qhtkd', 'mttnw3', 'xh3', 'mld', 'ycshz', 'ys1', 'woi2', 'rat', 'kskjb', 'mttnw4', 'xh4', 'tiag', 'qqwxk', 'mld2', 'ys2', 'mld3', 'ys3', 'atdf', 'ygdyj', 'dfv', 'kcsl', 'ultimate battle', 'mld4', 'ys4', 'ubtng', 'jzcsd', 'mld5', 'ys5', 'tgr', 'qhdyj', 'mld6', 'ys6', 'tst', 'ycsjc', 'mld7', 'ys7', 'moa', 'aysmy', "explore wolffy's mind", 'mld8', 'ys8', 'ewm', 'xsjqy', 'mld9', 'ys9', 'ch', 'fkcny', 'mld10', 'ys10', 'mwr', 'qxdyj', 'mld11', 'ys11', 'nwc', 'kyxyz', 'atwi20d', 'atwi2d', 'atwitd', 'xyyysb', 'epg', 'yydyxyy', 'mjt', 'mwmr', 'jrjjhtl', 'pgfc', 'pgfc1', 'zqyxt1', 'anp', 'ap', 'pgfc2', 'zqyxt2', 'saf', 'pgfc3', 'pgfctec', 'zqyxt3', 'tec', 'pgfc4', 'zqyxt4', 'tatw', 'pgfc5', 'zqyxt5', 'iw', 'pgfc6', 'zqyxt6', 'ft', 'mgs', 'yyqmx', 'mgs2', 'mgsii', 'yyqmx2', 'movie1', 'm1', 'tsa', 'nqct', 'movie2', 'm2', 'dttaotlt', 'hhsw', 'movie3', 'm3', 'mctsa', 'tndgg', 'movie4', 'm4', 'miaotdt', 'kxcln', 'movie5', 'm5', 'tma', 'xqyygsn', 'movie6', 'm6', 'mtp', 'fmqyj', 'movie7', 'm7', 'apg', 'ynxyy', 'movie8', 'm8', 'dff', 'kcwl', 'movie9', 'm9', 'twg', 'sh', 'movie10', 'm10', 'bnd', 'ygpx', 'live-action1', 'la1', 'ilw', 'wahtl', 'live-action2', 'la2', 'ilw2', 'wahtl2'
    ]
    # 用 join 拼成正则 alternation
    season_pattern = '|'.join(re.escape(s) for s in allowed_seasons)

    # 匹配模式：File:season + number + .png
    pattern = rf'^File:({season_pattern})(\d+)\.png$'

    match = re.match(pattern, title.lower(), flags=re.IGNORECASE)
    if match:
        season = match.group(1)
        number = match.group(2)  # 保留原样（可能有前导零）
        number = number.lstrip('0')
        ep = r'{{ep|' + season + '|' + number + '}}'
        return ep
    return None

def process_all_file_pages():
    for page in site.allpages(namespace=FILE_NS):
        title = page.title()
        try:
            if not page.exists():
                print(f"[SKIP] {title} does not exist.")
                continue
            text = page.text or ''
            if title.startswith('File:Act 0109'):
                print(f"[SKIP] {title} has been cleaned already.")
                continue
            if text.strip() == '':
                print(f"[BLANK] {get_url(title)} — empty file description. No automatic fix; please check manually.")
                input('Press Enter to continue...')
                continue

            leading, sections = split_headers(text)
            # normalize header titles lowercased
            header_titles = [s[1].strip().lower() for s in sections]

            # if any extra sections other than summary/licensing -> manual
            extras = [h for h in header_titles if h not in ('summary','licensing')]
            if extras:
                print(f"[MANUAL] {get_url(title)} — contains extra sections {extras}. No automatic fix; please check manually.")
                input('Press Enter to continue...')
                continue

            # CASE A: no headers at all
            if not sections:
                # create default Summary and Licensing, preserve original content as d=
                orig = text.rstrip('\n')
                new_text = "== Summary ==\n" + "{{fi|d=" + orig + "|s=}}\n\n" + "== Licensing ==\n{{Fairuse}}\n"
                if not equal_ignoring_trailing_single_newline(new_text, text):
                    if prompt_apply(title, text, new_text):
                        page.text = new_text
                        page.save(summary="autofix file description: default sections")
                        print(f"[FIXED] {title} — inserted default Summary and Licensing.")
                    else:
                        print(f"[SKIPPED] {title}")
                else:
                    print(f"[OK] {title} — already same.")
                continue

            # build map from lower title => section tuple
            sec_map = {s[1].strip().lower(): s for s in sections}

            # CASE B: only Licensing exists
            if 'licensing' in sec_map and 'summary' not in sec_map:
                lic_header_full, lic_title, lic_start, lic_end, lic_content = sec_map['licensing']
                # preserve licensing header format (lic_header_full)
                # keep original between text before licensing header (leading-> we treat separately)
                if parse_title(title):
                    ep = parse_title(title)
                    new_summary_header = "== Summary ==\n{{fi|d=Title card of " + ep + ".|s=" + ep + "}}\n"
                else:
                    new_summary_header = "== Summary ==\n{{fi|s=}}\n"
                # Determine the whitespace between our new summary block and existing licensing header:
                # if there was leading content (text before first header) keep it (should be empty here),
                # but ensure at most one blank line between summary and licensing: we'll use a single newline
                new_text = new_summary_header + lic_header_full + "\n" + lic_content.lstrip('\n')
                if not equal_ignoring_trailing_single_newline(new_text, text):
                    page.text = new_text
                    page.save(summary="autofix file description: default summary section")
                    print(f"[FIXED] {title} — added default Summary above Licensing.")
                    # if prompt_apply(title, text, new_text):
                    #     page.text = new_text
                    #     page.save(summary="autofix file description: default summary section")
                    #     print(f"[FIXED] {title} — added default Summary above Licensing.")
                    # else:
                    #     print(f"[SKIPPED] {title}")
                else:
                    print(f"[OK] {title} — no change needed.")
                continue

            # CASE C: leading text exists (text before first header) and no explicit Summary header
            first_header = sections[0]
            if leading and leading.strip() and 'summary' not in sec_map:
                # Move leading into Summary using Fi|d=
                orig_leading = leading.rstrip('\n')
                new_summary_block = "== Summary ==\n" + "{{fi|d=" + orig_leading + "|s=}}\n"
                # append all existing headers (we only expect Licensing now)
                remaining_blocks = []
                for header_full, title_name, start, end, content in sections:
                    # keep original header_full (preserve spacing) and content (but strip leading blank lines)
                    remaining_blocks.append(header_full + "\n" + content.lstrip('\n'))
                # ensure one blank line between summary block and next header if the original had one blank line
                between = '\n'
                new_text = new_summary_block + between + ("\n\n".join(remaining_blocks)).lstrip('\n')
                if not equal_ignoring_trailing_single_newline(new_text, text):
                    if prompt_apply(title, text, new_text):
                        page.text = new_text
                        page.save(summary="autofix file description: add summary section")
                        print(f"[FIXED] {title} — moved leading content into Summary.")
                    else:
                        print(f"[SKIPPED] {title}")
                else:
                    print(f"[OK] {title} — no change needed.")
                continue

            # CASE D: have both Summary and Licensing
            # ---- 快速基于原始文本的合规性检查（优先使用，不走后续分段重建） ----
            # 如果页面同时存在 Summary 与 Licensing 两个 header，直接从原始 text 提取对应 block 来判断，
            # 如果已完全合规就直接跳过（避免任何重写/重建导致空行变化）。
            if 'summary' in sec_map and 'licensing' in sec_map:
                raw_sum_block = extract_section_block_from_text(text, 'summary')
                raw_lic_block = extract_section_block_from_text(text, 'licensing')

                if raw_sum_block is not None and raw_lic_block is not None:
                    sum_ok, _ = section_is_single_template_whole(raw_sum_block, ALLOWED_SUMMARY_TEMPLATES)
                    lic_ok, _ = section_is_single_template_whole(raw_lic_block, ALLOWED_LICENSE_TEMPLATES)

                    # 允许 header 下方有 0 或 1 个空行（即不以两个或更多连续换行开头）
                    def header_blank_ok(block):
                        # block 以 '\n\n' 或更多换行开头表示 header 后至少有 2 个空行 -> 不允许
                        return not block.startswith('\n\n')

                    # Licensing 末尾多余空行的判断（与之前逻辑保持一致）
                    lic_ends_with_extra_blank = bool(re.search(r'\n\s*\Z', raw_lic_block)) and raw_lic_block.rstrip('\n') != raw_lic_block

                    if sum_ok and lic_ok and header_blank_ok(raw_sum_block) and header_blank_ok(raw_lic_block) and not lic_ends_with_extra_blank:
                        print(f"[OK] {title} — fully compliant; skipped.")
                        continue
            # ---- 如果不满足快速跳过条件，继续原有分段/清理逻辑 ----

            # fallback
            print(f"[MANUAL] {get_url(title)} — unusual structure, skipped. Please inspect manually.")
            input("Press Enter to continue...")

        except Exception as e:
            print(f"[ERROR] {get_url(title)} — {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    process_all_file_pages()
