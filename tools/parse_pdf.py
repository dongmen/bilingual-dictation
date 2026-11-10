import fitz, re, csv, json

PDF = r'D:/Users/chinalife/Desktop/U1-U3语言点汇总.pdf'
OUT_CSV = r'D:/WorkBuddy/2026-11-09-11-12-08/U1-U3语言点汇总_import.csv'

doc = fitz.open(PDF)
text = "\n".join(doc[i].get_text() for i in range(doc.page_count))

ZH = re.compile(r'[一-鿿]')
unit_re = re.compile(r'^U(\d+)')
num_re = re.compile(r'^\s*(\d+)\.\s*(.*)$')

pairs = []          # (group, en, zh)

def norm_en(s):
    # 弯引号 -> ASCII；省略号 -> 三个点（避免 CJK 字体下占位偏宽）
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('…', '...')
    s = re.sub(r'-\s+', '-', s)        # 去掉连字符后误拆的空格（Bird- watching -> Bird-watching）
    return s

def norm_zh(s):
    # 中文侧只把弯引号转 ASCII；省略号……是正常中文标点，保留
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = re.sub(r'(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])', '', s)  # 去掉汉字间换行误拆空格
    return s

# 原文笔误订正（来源 PDF 中的重复字）
ZH_FIX = {
    '它帮助我能更多地了了解自然': '它帮助我能更多地了解自然',
    '她想交朋友并和大家和分享写作的乐趣': '她想交朋友并和大家分享写作的乐趣',
}

def is_section_marker(x):
    return ('词组' in x) or ('句子' in x) or ('words and phrases' in x) or ('sentences' in x)

def clean_title(x):
    x = re.sub(r'^\s*\d+\.\s*', '', x)
    x = re.sub(r'\s+Textbook.*', '', x)
    return x.strip() or 'Lesson'

def split_en_zh(blob):
    blob = ' '.join(blob.split())
    if not ZH.search(blob):
        return norm_en(blob.strip()), ''
    # 中文 = CJK 汉字连续段（首汉字到末汉字）
    idxs = [i for i, ch in enumerate(blob) if ZH.match(ch)]
    zh = blob[idxs[0]: idxs[-1] + 1]
    # 英文 = 汉字段之外「最长的纯英文片段」（自动兼容 中前英后 / 英前中后 / 中文内嵌英文名）
    lat_runs = re.findall(r'[^\u4e00-\u9fff]+', blob)
    cand = [r.strip() for r in lat_runs if r.strip()]
    en = max(cand, key=len) if cand else ''
    en = norm_en(en)
    # 清掉英文首尾可能混入的中文标点 / 全角标点 / 空格
    en = re.sub(r'^[。，、；：！？…·\s]+', '', en)
    en = re.sub(r'[。，、；：！？…·\s]+$', '', en)
    # 中文省略号(…… -> 6点)残留清掉，英文省略号(… -> 3点)保留
    en = re.sub(r'\.{4,}\s*$', '', en)
    zh = norm_zh(zh)
    zh = ZH_FIX.get(zh, zh)
    return en.strip(), zh.strip()

def add_pair(group, blob):
    en, zh = split_en_zh(blob)
    if en and zh:
        pairs.append((group, en, zh))

# ---------- 按条目重组：编号行界定条目，章节标记/单位行跳过 ----------
lines = [l.strip() for l in text.splitlines() if l.strip()]
n = len(lines)
cur_unit = 'U?'
cur_section = 'Lesson'
entries = []      # (group, [lines])
cur = None        # 当前条目内容行

def flush():
    global cur
    if cur is not None and cur:
        # 去掉空字符串（如独占一行的编号）
        content = [c for c in cur if c]
        if content:
            entries.append((f'{cur_unit} {cur_section}', content))
    cur = None

for i, s in enumerate(lines):
    if unit_re.match(s):
        flush()
        cur_unit = 'U' + unit_re.match(s).group(1)
        cur_section = 'Lesson'
        continue
    if is_section_marker(s):
        continue  # 章节标题（Ⅰ/Ⅱ、一、二、words and phrases / sentences）跳过
    if s.strip() == '答案' or s.strip() == '单词&词组' or s.strip() == '词组':
        continue  # 栏目表头，跳过
    mm = num_re.match(s)
    if mm:
        rest = mm.group(2).strip()
        nxt = lines[i + 1] if i + 1 < n else ''
        nxt_is_marker = is_section_marker(nxt) or num_re.match(nxt) or nxt.strip() in ('答案', '单词&词组', '词组')
        if nxt_is_marker:
            # 编号行后接章节标记或下一课编号 -> 这是「课名」，不是词条
            cur_section = clean_title(mm.group(2)) or cur_section
            continue
        # 否则是词条起始
        flush()
        cur = [rest] if rest else []
        continue
    # 非编号内容行
    if cur is not None:
        cur.append(s)

flush()

# 每条目 pairing（group 已是完整「单位+课名」）
for group, content in entries:
    add_pair(group, ' '.join(content))

# 写 CSV（utf-8-sig 兼容 Excel）
with open(OUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['en', 'zh', 'group'])
    for g, en, zh in pairs:
        w.writerow([en, zh, g])

# 统计
from collections import Counter
cnt = Counter(g for g, _, _ in pairs)
print('总条目:', len(pairs))
print('分组数:', len(cnt))
for g, c in cnt.items():
    print(f'  {g}: {c}')

# 输出 JSON 供嵌入 HTML
with open(r'D:/WorkBuddy/2026-11-09-11-12-08/_seed.json', 'w', encoding='utf-8') as f:
    json.dump([[g, en, zh] for g, en, zh in pairs], f, ensure_ascii=False)

print('\n样例（前 6 条）:')
for g, en, zh in pairs[:6]:
    print(f'  [{g}] {en}  ||  {zh}')
print('\n样例（句子末 4 条）:')
for g, en, zh in pairs[-4:]:
    print(f'  [{g}] {en}  ||  {zh}')
