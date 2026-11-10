#!/usr/bin/env python3
"""Search the Chinese GIF action catalog and write director briefs for single GIFs or sticker packs."""
import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from string import Formatter

REFERENCES = Path(__file__).resolve().parents[1] / "references"
CATALOG = REFERENCES / "actions.json"
FAMILIES = {
    "greeting": "招呼与进退场", "affection": "亲密与安慰", "praise": "夸奖与认同",
    "gratitude": "感谢与礼数", "refusal": "拒绝与劝退", "awkward": "尴尬与社死",
    "sarcasm": "反讽与阴阳怪气", "laughter": "搞笑与憋笑", "shock": "惊讶与疑惑",
    "anger": "生气与抓狂", "sadness": "委屈与难过", "fatigue": "打工与疲惫",
    "anticipation": "围观与期待", "celebration": "庆祝与祝福", "absurd": "抽象与变形",
    "performance": "表演与舞动", "camera": "写真与运镜", "utility": "确认与状态",
    "meltdown": "发疯与崩坏", "work": "职场众生相", "food": "干饭与吃喝",
    "money": "钱包与暴富", "school": "校园与考试", "romance": "恋爱与暧昧",
    "family": "亲戚与家庭", "festival": "节日与节气", "gaming": "游戏与开黑",
    "petlife": "宠物日常", "chatplay": "聊天互动与热梗", "body": "身体与养生",
    "daily": "生活意外", "reply": "回消息", "progress": "工作进度", "company": "陪伴安慰",
    "status": "日常状态", "mood": "小情绪", "textplay": "文字动效", "photoreal": "写实整活",
    "christmas": "圣诞与平安夜", "newyear": "元旦与跨年", "spring": "春节",
}
SUBJECTS = {"human", "mascot", "pet", "object", "text"}
LOOPS = {
    "reset": "爆点过后，让主体用动作回到准备姿态",
    "match": "用方向、轮廓或构图匹配最后一拍与开头",
    "pingpong": "往返播放可逆动作，转折端点只保留一次",
    "occlusion": "利用自然遮挡，在遮满的瞬间接回开场",
    "cycle": "连续做完整周期，最后一帧与下一轮第一帧相邻",
    "hold": "读懂爆点后留一拍，在明确的节奏点切回开头",
}
GAGS = {
    "contrast": ("反差", "表面和内心、可爱和崩溃同框，一方始终不变，另一方越来越离谱"),
    "escalation": ("升级", "同一件事重复，每次加码，在最夸张处突然收住"),
    "collapse": ("崩坏", "身体或物件的物理规则失效，形变要明确；可停在结果硬切回开头，不强求回弹"),
    "deadpan": ("冷面", "主体不动声色，把最长的停顿留给观众自己领会"),
    "reversal": ("反转", "前两拍建立预期，最后一拍打破它，反转前不要提前泄露"),
    "literal": ("字面", "把口语按字面意思真的演出来"),
    "scale": ("尺度", "大小、数量或时间严重失衡"),
    "sincere": ("真诚", "这张不靠笑点，动作清楚、情绪真实即可"),
}
INTENSITIES = {
    "restrained": ("克制", "位移小，眼神和细节先动，可以直接发给不太熟的人"),
    "exaggerated": ("夸张", "位移大，反应带弹性，全身参与，道具也跟着动"),
    "absurd": ("抽象", "打破物理规则，身体可以裂、融、炸、飞；允许停在结果硬切，不强求回弹"),
}
AUDIENCES = {
    "safe": "工作群和长辈群也能发",
    "casual": "朋友和熟同事可用，正式工作群慎用",
    "close": "只建议发给熟人，对上级或陌生人可能被读成冒犯",
}
REFERENCE_IDENTITY = ("身份锚点：把原图作为实际图像输入，保留原人物的基础特征、面部与发型线索、轮廓和辨识度，"
                      "让人看得出来自本人；不能只保留衣服颜色就换成泛用角色。宠物和物件保留各自最显眼的识别特征。")
PHOTO_STYLE = ("明确选择写实照片：保留真实照片的材质、光线和镜头质感；表情、姿态和动作仍可大胆表演，"
               "不要把参考人物冻结在原姿势。")
STYLIZED_REFERENCE = ("参考图不锁画风：默认允许跨画风、夸张表情、比例变化和形变，在改造中保留身份线索。")
REFERENCE_DELIVERY = "若生成后明显丢失身份，如实说明；不为逐帧一致性反复精修，也不自动补抽。"
MOTIONS = {"action": "连续动作", "light": "轻动"}
PRESETS = {"breathe", "nod", "bounce", "sway", "shake", "tremble", "pop", "lean"}
STYLE_GROUPS = {"pixel": "像素", "illustration": "插画", "photo": "照片"}
# Who the sticker is sent to decides which audience marks are acceptable.
RECIPIENTS = {"boss": {"safe"}, "work": {"safe"}, "elder": {"safe"}, "stranger": {"safe"},
              "friend": {"safe", "casual"}, "colleague": {"safe", "casual"},
              "close": {"safe", "casual", "close"}, "partner": {"safe", "casual", "close"}}
FAMILY_HINTS = {
    "laughter": ("搞笑", "爆笑", "好笑"), "absurd": ("抽象", "荒诞", "离谱"),
    "camera": ("多镜头", "运镜", "写真镜头"), "sarcasm": ("阴阳怪气", "反讽"),
    "fatigue": ("疲惫", "困倦"), "awkward": ("尴尬", "社死"),
    "celebration": ("庆祝", "祝福"), "anticipation": ("围观", "等瓜"),
    "meltdown": ("发疯", "崩溃"), "work": ("打工", "上班", "职场"),
    "food": ("吃货", "美食"), "gaming": ("游戏",), "romance": ("恋爱", "情侣"),
    "petlife": ("猫猫", "狗狗", "宠物", "猫咪", "主子"), "school": ("学生", "校园"),
    "christmas": ("圣诞", "平安夜"), "newyear": ("跨年", "元旦"), "spring": ("春节", "过年", "拜年", "新春"),
}


def load(name):
    return json.loads((REFERENCES / name).read_text(encoding="utf-8"))


def validate(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("动作库须为非空数组")
    seen = set()
    for n, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"第 {n} 条不是对象")
        for key in ("id", "name", "family", "mood", "camera", "loop", "gag", "intensity", "audience"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"第 {n} 条字段无效: {key}")
        key = row["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) or key in seen:
            raise ValueError(f"重复或无效的 ID: {key}")
        seen.add(key)
        if row["family"] not in FAMILIES or row["loop"] not in LOOPS:
            raise ValueError(f"无效类别或回环类型: {key}")
        if row["gag"] not in GAGS or row["intensity"] not in INTENSITIES or row["audience"] not in AUDIENCES:
            raise ValueError(f"无效笑点、强度或适用关系: {key}")
        if row.get("motion") not in MOTIONS or not isinstance(row.get("photo"), bool):
            raise ValueError(f"缺少动法或照片标记: {key}")
        if (row["motion"] == "light") != (row.get("preset") in PRESETS):
            raise ValueError(f"轻动卡必须有有效预设，连续动作卡不能有: {key}")
        for field in ("aliases", "beat", "subjects"):
            values = row.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"{key} 缺少 {field}")
        if len(row["beat"]) != 3 or not set(row["subjects"]) <= SUBJECTS:
            raise ValueError(f"检查 {key} 的三拍或主体")
    # A pair is two stickers sent one after the other; both halves must point at each other.
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        pair = row.get("pair")
        if pair is None:
            continue
        partner = by_id.get(pair.get("with")) if isinstance(pair, dict) else None
        if (not partner or pair.get("step") not in (1, 2) or not isinstance(partner.get("pair"), dict)
                or partner["pair"].get("with") != row["id"] or partner["pair"].get("step") + pair["step"] != 3):
            raise ValueError(f"组合表情无效: {row['id']}")


def validate_layers(rows, styles, trends, packs):
    ids = {row["id"] for row in rows}
    style_ids = {style["id"] for style in styles}
    if len(style_ids) != len(styles):
        raise ValueError("风格 ID 重复")
    for style in styles:
        if not all(isinstance(style.get(k), str) and style[k].strip() for k in ("id", "name", "look", "fits", "avoid")):
            raise ValueError(f"风格字段不全: {style.get('id')}")
        if style.get("group") not in STYLE_GROUPS:
            raise ValueError(f"风格大类无效: {style['id']}")
    for entry in trends["terms"]:
        missing = set(entry["actions"]) - ids
        if missing or not entry["actions"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", entry["added"]):
            raise ValueError(f"热梗 {entry['term']} 无效：{sorted(missing) or '缺动作或日期'}")
    if len({pack["id"] for pack in packs}) != len(packs):
        raise ValueError("表情包 ID 重复")
    for pack in packs:
        missing = set(pack["actions"]) - ids
        if missing or pack["style"] not in style_ids or len(set(pack["actions"])) != len(pack["actions"]):
            raise ValueError(f"表情包 {pack['id']} 无效：{sorted(missing) or '风格错误或动作重复'}")
        season = pack.get("season")
        if season is not None and (not isinstance(season, dict) or not str(season.get("label", "")).strip()
                                   or not all(re.fullmatch(r"(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", str(season.get(k, "")))
                                              for k in ("from", "to"))):
            raise ValueError(f"表情包 {pack['id']} 的适用时段无效")


def validate_templates(templates):
    """Validate reusable pose skeletons without prescribing a pack or frame count."""
    if not isinstance(templates, list) or not templates:
        raise ValueError("姿势模板须为非空数组")
    seen = set()
    for n, row in enumerate(templates, 1):
        if not isinstance(row, dict):
            raise ValueError(f"第 {n} 个姿势模板不是对象")
        key = row.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) or key in seen:
            raise ValueError(f"重复或无效的模板 ID: {key}")
        seen.add(key)
        if not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError(f"模板名称无效: {key}")
        for field in ("intents", "poses"):
            values = row.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"模板 {key} 缺少 {field}")
        if len(row["poses"]) < 2:
            raise ValueError(f"模板 {key} 至少需要两个关键姿势")
        for field, required in (("slots", {"subject", "prop", "feature"}),
                                ("variants", {"exaggerated", "absurd"}),
                                ("adaptations", {"human", "pet", "object"})):
            values = row.get(field)
            if (not isinstance(values, dict) or not required <= values.keys()
                    or not all(isinstance(v, str) and v.strip() for v in values.values())):
                raise ValueError(f"模板 {key} 的 {field} 无效")
        for pose in row["poses"]:
            try:
                fields = list(Formatter().parse(pose))
            except ValueError:
                raise ValueError(f"模板 {key} 的槽位括号无效") from None
            if any(field is not None and (field not in row["slots"] or spec or conversion)
                   for _, field, spec, conversion in fields):
                raise ValueError(f"模板 {key} 引用了未知槽位或不支持的格式")
        timing = row.get("timing")
        if not isinstance(timing, dict) or timing.get("loop") not in LOOPS:
            raise ValueError(f"模板 {key} 的回环类型无效")
        holds = timing.get("holds_ms")
        if (not isinstance(holds, list) or len(holds) != len(row["poses"])
                or not all(type(v) is int and v > 0 and v % 10 == 0 for v in holds)):
            raise ValueError(f"模板 {key} 的姿势停顿须与姿势一一对应，且为正的 10 毫秒倍数")
        if not isinstance(timing.get("note"), str) or not timing["note"].strip():
            raise ValueError(f"模板 {key} 缺少节拍说明")


def apply_trends(rows, trends):
    """Search trend terms as aliases, without storing them on the action cards."""
    by_id = {row["id"]: row for row in rows}
    for entry in trends["terms"]:
        for action in entry["actions"]:
            by_id[action].setdefault("trend_terms", []).append(entry["term"])


def normal(text):
    return re.sub(r"[^a-z0-9㐀-鿿]+", "", unicodedata.normalize("NFKC", text).lower())


def grams(s):
    return {s[i:i+2] for i in range(len(s)-1)}


def score(query, row):
    own = [normal(x) for x in [row["name"], row["id"], *row["aliases"]]]
    # IDs only match exactly: "ddl" must not hit the middle of "teardrop-puddle".
    primary = [normal(x) for x in [row["name"], *row["aliases"], *row.get("trend_terms", [])]]
    if query in own:
        return 200 + len(query)
    if query in primary:  # A card's own words outrank the trend layer's suggestions.
        return 150 + len(query)
    matches = {s for s in primary if len(s) >= 2 and s in query}
    partial = [len(query) for s in primary if len(query) >= 2 and query in s]
    grams_query = grams(query)
    overlap = max((len(grams_query & grams(s)) for s in primary), default=0)
    if matches or partial:
        longest = max([len(s) for s in matches] + partial)
        # A second independent cue matters; "探头吃瓜" should beat plain "探头".
        extra = sum(1 for s in matches if not any(s != v and s in v for v in matches))
        return 70 + 7 * longest + 5 * extra + overlap
    if overlap >= 2:
        return 10 + overlap
    hints = FAMILY_HINTS.get(row["family"], ())
    if any(h in query for h in hints) or query in normal(FAMILIES[row["family"]]) or query == normal(row["family"]):
        return 8
    return 0


def output_spec(row):
    return ("输出：本款只生成一次，直接交付独立可播放的循环动图 GIF 文件。画幅按动作构图决定；"
            "用关键姿势与停顿表达意思，不统一帧数和时长。")


def style_line(style, label="风格"):
    return f"{label}：{style['name']}。{style['look']}。避免：{style['avoid']}。"


def reference_lines(style, photo_ref):
    if not photo_ref:
        return ["有参考图时实际传入原图，保留最显眼的识别特征，按表达意图选择画风和演法；没有指定形象时可自拟原创角色。"]
    return [REFERENCE_IDENTITY,
            PHOTO_STYLE if style and style["id"] == "photo-real" else STYLIZED_REFERENCE,
            REFERENCE_DELIVERY]


def character_line(character=None, photo_ref=False):
    if character:
        return f"角色：{character}。保留文字指定的主体与辨识特征；未指定的细节和画风可自由发挥。"
    if photo_ref:
        return "角色：沿用参考图主体，留住面部、发型或该主体独有的识别线索，允许表情、比例和姿态为表达服务。"
    return "角色：未指定，可自由设计；整组可以更换主体，不默认绑定同一角色或画风。"


def brief(row, style=None, intensity=None, photo_ref=False, character=None):
    labels = ("起势", "爆点", "回环")
    level = intensity or row["intensity"]
    gag_name, gag_rule = GAGS[row["gag"]]
    lines = ([*reference_lines(style, True), ""] if photo_ref else []) + [f"{row['name']}  [{row['id']}]",
             character_line(character, photo_ref),
             f"语气：{row['mood']}。适配主体：{', '.join(row['subjects'])}。",
             f"笑点：{gag_name}。{gag_rule}。",
             f"强度：{INTENSITIES[level][0]}。{INTENSITIES[level][1]}。"]
    if intensity and intensity != row["intensity"]:
        lines.append(f"这张卡原本写的是{INTENSITIES[row['intensity']][0]}档，按上面的强度放大或收敛三拍，不改变动作意图。")
    lines.append(f"适用关系：{AUDIENCES[row['audience']]}。")
    lines += [f"{label}：{beat}" for label, beat in zip(labels, row["beat"])]
    lines += [f"机位：{row['camera']}", f"循环指令：{LOOPS[row['loop']]}。", output_spec(row)]
    if row.get("pair"):
        partner = row["pair"]["with"]
        lines.append(f"组合表情：这是两张连发的第 {row['pair']['step']} 张，另一张是 [{partner}]。两张都要做，按顺序交付，并告诉用户连着发。")
    if style:
        lines.append(style_line(style))
    if row["motion"] == "light":
        lines.append(f"动法参考：可用少量关键姿势表达；轻动预设 {row['preset']} 仅供明确要求轻动时选用。")
    if not photo_ref:
        lines += reference_lines(style, False)
    return "\n".join(lines)


def template_brief(template, style=None, character=None, prop=None, subject=None,
                   intensity=None, photo_ref=False, extra_slots=None):
    slots = dict(template["slots"])
    slots.update(extra_slots or {})
    if character:
        slots["subject"] = character
    if prop:
        slots["prop"] = prop
    lines = ([*reference_lines(style, True), ""] if photo_ref else []) + [
        f"{template['name']}  [{template['id']}]",
        character_line(character, photo_ref),
        f"适用意图：{' / '.join(template['intents'])}",
        "这是可复用的姿势骨架，可替换主体、道具和语境；不是固定组图清单。",
        "可替换槽位：" + "；".join(f"{key}={value}" for key, value in slots.items()),
        "关键姿势："]
    for n, pose in enumerate(template["poses"], 1):
        lines.append(f"  {n}. {pose.format_map(slots)}")
    adaptations = template["adaptations"]
    if subject:
        adaptation = adaptations.get(subject, "沿用最接近的动作结构，把手脚动作换成该主体可读的轮廓变化。")
        lines.append(f"主体适配（{subject}）：{adaptation}")
    else:
        lines += [f"主体适配（{kind}）：{text}" for kind, text in adaptations.items()]
    if intensity == "restrained":
        lines.append("克制变体：保留停顿和态度，只缩小动作幅度，不把关键姿势删掉。")
    else:
        levels = [intensity] if intensity else ["exaggerated", "absurd"]
        lines += [f"{INTENSITIES[level][0]}变体：{template['variants'][level]}" for level in levels]
    timing = template["timing"]
    lines.append("节拍建议：关键姿势依次停留 " + "/".join(map(str, timing["holds_ms"])) +
                 f" 毫秒；{timing['note']}。这是设计建议，不是平台标准或必须生成的帧数。")
    lines.append(f"回环：{LOOPS[timing['loop']]}。")
    if style:
        lines.append(style_line(style))
    lines.append(output_spec(template))
    if not photo_ref:
        lines += reference_lines(style, False)
    return "\n".join(lines)


def pack_brief(pack, rows, style, character, photo_ref=False, style_explicit=False):
    by_id = {row["id"]: row for row in rows}
    cards = [by_id[action] for action in pack["actions"]]
    reference_style = style if style_explicit else None
    style_label = "风格" if style_explicit else "候选风格起点（可跨风格组合，不默认整组统一）"
    lines = ([*reference_lines(reference_style, True), ""] if photo_ref else []) + [f"# {pack['name']}（{len(cards)} 张）· {pack['for']}", "",
             character_line(character, photo_ref),
             style_line(style, style_label),
             "整组围绕用途选择反应；构图、形变、节拍随每张的态度变化，每张突出一个意思。",
             "以下是该包的完整候选清单；默认交付数量由 SKILL.md 决定，用户明确要求整包或指定数量时按要求执行。",
             "每款只生成一次，每张交付独立可播放的循环动图 GIF 文件，直接合成并交付。",
             *([f"适用时段：{pack['season']['label']}，约 {pack['season']['from']} 至 {pack['season']['to']}；过了这个时段不主动推荐。"]
               if pack.get("season") else []), ""]
    for n, row in enumerate(cards, 1):
        lines.append(f"{n:02d}. {row['name']} [{row['id']}]｜笑点：{GAGS[row['gag']][0]}｜{INTENSITIES[row['intensity']][0]}"
                     f"｜{AUDIENCES[row['audience']]}")
        lines.append(f"    {row['beat'][0]} → {row['beat'][1]} → {row['beat'][2]}")
        lines.append(f"    机位：{row['camera']} 循环：{LOOPS[row['loop']]}。")
        lines.append(f"    {output_spec(row)}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="中文口语、别名或动作名")
    parser.add_argument("--family", choices=FAMILIES)
    parser.add_argument("--subject", choices=sorted(SUBJECTS))
    parser.add_argument("--gag", choices=GAGS, help="按笑点机制筛选")
    parser.add_argument("--audience", choices=AUDIENCES, help="按适用关系筛选")
    parser.add_argument("--intensity", choices=INTENSITIES, help="筛选强度；与 --brief 同用时改为按此强度导演")
    parser.add_argument("--style", help="风格 ID，配合 --brief、--pack 或 --template")
    parser.add_argument("--motion", choices=MOTIONS, help="按动法筛选")
    parser.add_argument("--photo-ok", action="store_true", help="可选自然实拍筛选：只看自然比例动作；不是上传真人参考的默认限制")
    parser.add_argument("--to", choices=RECIPIENTS, help="发给谁，自动过滤不合适的卡")
    parser.add_argument("--photo-ref", action="store_true",
                        help="传入真人或宠物参考，保留身份线索；默认允许跨画风和夸张形变，仅 --style photo-real 锁照片质感")
    parser.add_argument("--pack", help="输出成套表情包的导演说明")
    parser.add_argument("--character", help="--brief、--pack 或 --template 使用的主体及文字特征；不默认绑定画风")
    parser.add_argument("--prop", help="--template 中替换的道具")
    parser.add_argument("--slot", action="append", default=[], metavar="名=值",
                        help="替换模板里的任意槽位，可重复，例如 --slot zodiac=马")
    parser.add_argument("--template", help="展开指定的可复用姿势模板")
    parser.add_argument("--list-templates", action="store_true", help="列出可复用姿势模板")
    parser.add_argument("--list-styles", action="store_true", help="列出风格库")
    parser.add_argument("--list-packs", action="store_true", help="列出成套表情包")
    parser.add_argument("--id", help="精确动作 ID")
    parser.add_argument("--brief", action="store_true", help="展开首选动作的导演说明")
    parser.add_argument("--list", action="store_true", help="列出所有匹配动作")
    parser.add_argument("--check", "--validate", dest="check", action="store_true", help="检查动作、风格、套包和姿势模板结构并统计覆盖")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    try:
        rows, styles, trends, packs = load("actions.json"), load("styles.json"), load("trends.json"), load("packs.json")
        templates = load("motion-templates.json")
        validate(rows)
        validate_layers(rows, styles, trends, packs)
        validate_templates(templates)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error)+"\n")
    apply_trends(rows, trends)
    styles_by_id = {style["id"]: style for style in styles}
    if args.style and args.style not in styles_by_id:
        parser.error(f"未知风格：{args.style}；用 --list-styles 查看")
    if args.check:
        counts = Counter(row["family"] for row in rows)
        print(f"{len(rows)} 个动作 · {len(counts)} 类 · {len(styles)} 种风格 · {len(packs)} 套表情包 · {len(trends['terms'])} 条热梗 · {len(templates)} 个姿势模板")
        for family, title in FAMILIES.items():
            print(f"{family:14} {title}  {counts[family]}")
        return 0
    if args.list_templates:
        if args.json:
            print(json.dumps(templates, ensure_ascii=False, indent=2))
        else:
            for template in templates:
                print(f"{template['id']:22} {template['name']} · {' / '.join(template['intents'])}")
        return 0
    if args.template:
        template = next((t for t in templates if t["id"] == args.template), None)
        if not template:
            parser.error(f"未知姿势模板：{args.template}；用 --list-templates 查看")
        if args.json:
            print(json.dumps(template, ensure_ascii=False, indent=2))
        else:
            extra = {}
            for item in args.slot:
                name, sep, value = item.partition("=")
                if not sep or name not in template["slots"] or not value.strip():
                    parser.error(f"--slot 须为模板已有的槽位，例如 zodiac=马；本模板可用：{', '.join(template['slots'])}")
                extra[name] = value.strip()
            print(template_brief(template, styles_by_id.get(args.style), args.character, args.prop,
                                 args.subject, args.intensity, args.photo_ref, extra))
        return 0
    if args.list_styles:
        for group, title in STYLE_GROUPS.items():
            print(f"【{title}】")
            for style in (s for s in styles if s["group"] == group):
                print(f"{style['id']:14} {style['name']} · 适合：{style['fits']}")
        return 0
    if args.list_packs:
        for pack in packs:
            season = f" · 适用：{pack['season']['label']}" if pack.get("season") else ""
            print(f"{pack['id']:18} {pack['name']} · {len(pack['actions'])} 张 · {pack['for']}{season}")
        return 0
    if args.pack:
        pack = next((p for p in packs if p["id"] == args.pack), None)
        if not pack:
            parser.error(f"未知表情包：{args.pack}；用 --list-packs 查看")
        # The photo-real pack promises real people; every other pack's style is only a starting point.
        print(pack_brief(pack, rows, styles_by_id[args.style or pack["style"]], args.character,
                         args.photo_ref, bool(args.style) or pack["style"] == "photo-real"))
        return 0
    if args.limit < 1:
        parser.error("--limit 应为正数")
    # With --brief, --intensity directs the chosen card rather than filtering the catalog.
    level_filter = None if args.brief else args.intensity
    rows = [r for r in rows if (not args.family or r["family"] == args.family)
            and (not args.motion or r["motion"] == args.motion)
            and (not args.photo_ok or r["photo"])
            and (not args.to or r["audience"] in RECIPIENTS[args.to])
            and (not args.subject or args.subject in r["subjects"])
            and (not args.gag or r["gag"] == args.gag)
            and (not args.audience or r["audience"] == args.audience)
            and (not level_filter or r["intensity"] == level_filter)
            and (not args.id or args.id == r["id"])]
    if args.query:
        q = normal(args.query)
        ranked = [(score(q, r), r) for r in rows] if q else []
        rows = [r for weight, r in sorted(ranked, key=lambda v: -v[0]) if weight > 0]
    elif not (args.list or args.id or args.family or args.subject or args.gag or args.audience or args.intensity
              or args.motion or args.photo_ok or args.to):
        parser.error("提供动作描述，或使用 --list / --check")
    if not rows:
        print("没有匹配的动作。词库不可能穷尽说法：判断这句话的意图后，用 --family 或 --gag 找相近动作，或参照 references/comedy.md 按起势、爆点、回环即兴编排。", file=sys.stderr)
        return 1
    if not args.list:
        rows = rows[:args.limit]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif args.brief:
        if args.query:
            print(f"用户原句：{args.query}")
        # photoreal cards are staged for real photos, so they default to that medium.
        default_style = "photo-real" if rows[0]["family"] == "photoreal" else None
        style = styles_by_id.get(args.style or default_style)
        print(brief(rows[0], style, args.intensity, args.photo_ref, args.character))
        if args.query:
            print("如有多个连续动作、否定指令或指定镜头，逐项写入分镜，保留原句中的顺序与要求。")
    else:
        for r in rows:
            print(f"{r['id']:25} {r['name']}  · {FAMILIES[r['family']]}  · {GAGS[r['gag']][0]}/{INTENSITIES[r['intensity']][0]}"
                  f"  · {' / '.join(r['aliases'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
