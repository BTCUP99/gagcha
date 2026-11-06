#!/usr/bin/env python3
"""Rebuild the human-readable catalog from action cards and editorial evidence links."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/"skills"/"gif-actions"
sys.path.insert(0,str(SKILL/"scripts"))
from action import AUDIENCES, FAMILIES, GAGS, INTENSITIES, MOTIONS, STYLE_GROUPS, validate, validate_layers, validate_templates

AUDIENCE_SHORT={"safe":"工作群可用","casual":"朋友同事","close":"仅熟人"}

def read(name):
    return json.loads((SKILL/"references"/name).read_text(encoding="utf-8"))

def main():
    cards,styles,trends,packs=read("actions.json"),read("styles.json"),read("trends.json"),read("packs.json")
    templates=read("motion-templates.json")
    validate(cards)
    validate_layers(cards,styles,trends,packs)
    validate_templates(templates)
    if set(AUDIENCE_SHORT)!=set(AUDIENCES):
        raise ValueError("适用关系标签与 action.py 不一致")
    evidence=read("evidence.json")
    linked,sources=evidence["actions"],evidence["sources"]
    ids={card["id"] for card in cards}
    if set(linked)-ids or any(tag not in sources for refs in linked.values() for tag in refs):
        raise ValueError("证据索引含无效动作 ID 或来源")
    lines=["# 中文 GIF 动作图鉴","",f"{len(cards)} 张动作卡 · {len(set(c['family'] for c in cards))} 类 · {len(styles)} 种风格 · {len(templates)} 个动作模板 · {len(packs)} 套表情包。每张卡给出可见的爆点与三拍建议；用技能命令 `python scripts/action.py --id 动作ID --brief` 查看。","",
           "新创作没说数量时先确认做 6 款还是 9 款，用户明确指定的数量优先。已有成品的改字、调速等局部修改只处理指定文件，本地处理优先；有干净源帧时换字幕不再生成。九宫格是成品 GIF 的集中预览，不是 9 帧或静态候选。新创作每款一次生成尝试，只做一次自动编码与可播放检查；不先出锚点、不等前三张确认、不自动重抽或反复视觉修补。失败项如实列出，其余款继续。","",
           "可按同一句话多种演法、同主体多种反应、同场景多种用途组织，也可组合。动作卡负责聊天语义，模板负责姿势骨架，笑点手册负责口语气质与笑点，风格库负责视觉，场景包负责可用回复。一组不是固定模板组合。输入与修改边界见[需求理解](skills/gif-actions/references/requests.md)。","",
           "依据栏标识该表达有何参照，表里的分镜均由项目创作。标为“创作提案”的动作没有附带平台流行度的断言。",""]
    for code,source in sources.items():
        lines.append(f"- **{code}** {source['meaning']} [{source['name']}]({source['url']})")
    lines+=["","笑点机制："+"、".join(f"**{name}**（{rule}）" for name,rule in GAGS.values()),"",
            "强度："+"、".join(f"**{name}**（{rule}）" for name,rule in INTENSITIES.values()),"",
            "适用关系只是默认建议，发送前仍要看对象和语境。",""]
    lines+=["“自然实拍”是旧 `photo` 字段的可选筛选：表示按自然身体比例可演，不是人物参考图的准入条件，也不锁定画风。有原图时每次生成都实际传入，默认保留基本特征与轮廓辨识，同时允许跨画风、颜艺和变形；明确要求写实才限定媒介，写实也可以大胆表演。","",
            "动作可用少量关键姿势、粗跳、停顿和硬切表达，不要求平滑连续。表中“轻动”表示一个姿势就能读懂并兼容轻动，只有用户明确要轻动时才采用，不作为失败后的自动替代。",""]
    lines+=["## 风格库","","| 风格／ID | 大类 | 适合 | 视觉 |","| --- | --- | --- | --- |"]
    lines+=[f"| **{s['name']}** · `{s['id']}` | {STYLE_GROUPS[s['group']]} | {s['fits']} | {s['look']} |" for s in styles]
    lines+=["","## 动作模板","",
            "模板复用关键姿势与节奏骨架，可替换角色、道具、语气和风格。一组作品不是固定模板组合。用 `python scripts/action.py --list-templates` 查看列表，用 `python scripts/action.py --template snap-freeze` 展开。","",
            "| 模板／ID | 适用意图 | 关键姿势数 | 回环 | 可替换槽位 |","| --- | --- | ---: | --- | --- |"]
    lines+=[f"| **{t['name']}** · `{t['id']}` | {'、'.join(t['intents'])} | {len(t['poses'])} | `{t['timing']['loop']}` | {'、'.join(t['slots'])} |" for t in templates]
    lines+=["","## 成套表情包","",
            "每个包是一组候选动作，候选数不覆盖用户本次要求或默认交付数量。","",
            "| 表情包／ID | 候选数 | 默认风格 | 适合 |","| --- | ---: | --- | --- |"]
    style_names={s["id"]:s["name"] for s in styles}
    lines+=[f"| **{p['name']}** · `{p['id']}` | {len(p['actions'])} | {style_names[p['style']]} | {p['for']} |" for p in packs]
    lines+=["","## 动作分类","","| 场景 | 收录 |","| --- | ---: |"]
    for family,title in FAMILIES.items():
        subset=[c for c in cards if c["family"]==family]
        lines.append(f"| [{title}](#{family}) | {len(subset)} |")
    for family,title in FAMILIES.items():
        lines+=["",f'<a id="{family}"></a>',"",f"## {title}","","| 动作／ID | 可以这样说 | 爆点 | 笑点／强度 | 适用 | 动法 | 自然实拍 | 表达依据 |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for card in cards:
            if card["family"]!=family:
                continue
            tags="、".join(linked.get(card["id"],[])) or "创作提案"
            lines.append(f"| **{card['name']}** · `{card['id']}` | {'、'.join(card['aliases'])} | {card['beat'][1]} | "
                         f"{GAGS[card['gag']][0]}／{INTENSITIES[card['intensity']][0]} | {AUDIENCE_SHORT[card['audience']]} | {MOTIONS[card['motion']]} | {'可' if card['photo'] else '否'} | {tags} |")
    terms=sorted(trends["terms"],key=lambda t:t["term"])
    names={c["id"]:c["name"] for c in cards}
    lines+=["",'<a id="trends"></a>',"","## 热梗层","",trends["_about"],"","| 说法 | 意思 | 对应动作 | 收录日期 |","| --- | --- | --- | --- |"]
    lines+=[f"| {t['term']} | {t['meaning']} | {'、'.join(names[a] for a in t['actions'])} | {t['added']} |" for t in terms]
    (ROOT/"CATALOG.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

if __name__=="__main__":
    main()
