"""Exercise real one-line requests, and the style, pack and trend layers."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/"skills"/"gagcha"/"scripts"/"action.py"

def run(*args):
    return subprocess.run([sys.executable,SCRIPT,*args],capture_output=True,text=True,encoding="utf-8")

class ActionRoutingTests(unittest.TestCase):
    def first(self, query, *filters):
        result=subprocess.run([sys.executable,SCRIPT,query,*filters,"--json","--limit","1"],
                              capture_output=True,check=True,text=True,encoding="utf-8")
        return json.loads(result.stdout)[0]["id"]

    def test_peek_and_retreat_in_one_sticker(self):
        self.assertEqual(self.first("猫在桌边探头吃瓜，被发现了缩回去","--subject","pet"),
                         "desk-peek-melon-retreat")

    def test_multi_camera_keeps_actor_and_motion(self):
        self.assertEqual(self.first("沿用上一张真人参考，走过栏杆、转肩，想要明显的多镜头",
                                    "--subject","human","--family","camera"),
                         "three-camera-railing-walk")

    def test_hiding_prop_does_not_mean_switching_a_window(self):
        self.assertEqual(self.first("同事路过时慌忙收起摸鱼道具"),"desk-hide-slack-prop")
        self.assertEqual(self.first("老板来了秒切"),"boss-coming-tab-switch")

    def test_common_phrases_that_used_to_miss(self):
        for phrase,expected in {"破防了":"defense-broken-shatter","画大饼":"pie-in-the-sky","甩锅":"blame-pot-throw",
                                "干饭":"dry-rice-charge","暴富":"get-rich-rain","挂科":"fail-grade-stamp",
                                "亲亲":"kiss-mwah-heart","催婚":"marriage-push-relatives","中秋快乐":"mid-autumn-moon-bite",
                                "上分":"ranked-climb-fall","哈气":"cat-hiss-puff","功德+1":"wooden-fish-merit",
                                "鸽了":"pigeon-stood-up","失眠":"insomnia-counting-sheep","塞车":"traffic-jam-cartoon"}.items():
            self.assertEqual(self.first(phrase),expected,phrase)

    def test_trend_layer_is_searchable_but_stays_off_the_cards(self):
        self.assertIn(self.first("牛马"),{"newbie-holds-everything","overtime-window-moon","melt-over-desk"})
        cards=json.loads((SCRIPT.parents[1]/"references"/"actions.json").read_text(encoding="utf-8"))
        self.assertFalse(any("trend_terms" in card for card in cards))

    def test_query_does_not_match_inside_an_english_id(self):
        self.assertNotEqual(run("ddl","--limit","1").stdout.split()[:1],["teardrop-puddle"])
        self.assertEqual(self.first("teardrop-puddle"),"teardrop-puddle")

    def test_recipient_filter_hides_cards_that_could_offend(self):
        rows=json.loads(run("--to","boss","--list","--json").stdout)
        self.assertEqual({r["audience"] for r in rows},{"safe"})
        self.assertGreater(len(json.loads(run("--to","close","--list","--json").stdout)),len(rows))

    def test_optional_natural_photo_filter_excludes_deforming_cards(self):
        rows=json.loads(run("--photo-ok","--list","--json").stdout)
        ids={r["id"] for r in rows}
        self.assertTrue(all(r["photo"] and r["gag"]!="collapse" and r["intensity"]!="absurd" for r in rows))
        self.assertIn("rp-office-sinking",ids)
        self.assertNotIn("smug-chin-up",ids)

    def test_photo_reference_does_not_filter_action_search(self):
        baseline=json.loads(run("--list","--json").stdout)
        referenced=json.loads(run("--photo-ref","--list","--json").stdout)
        self.assertEqual([r["id"] for r in baseline],[r["id"] for r in referenced])
        self.assertTrue(any(not r["photo"] for r in referenced))

    def test_photo_reference_can_opt_into_natural_photo_filter(self):
        rows=json.loads(run("--photo-ref","--photo-ok","--list","--json").stdout)
        self.assertTrue(rows)
        self.assertTrue(all(r["photo"] for r in rows))

    def test_filters_combine(self):
        rows=json.loads(run("--gag","collapse","--audience","safe","--list","--json").stdout)
        self.assertTrue(rows)
        self.assertTrue(all(r["gag"]=="collapse" and r["audience"]=="safe" for r in rows))

class BriefTests(unittest.TestCase):
    def test_brief_keeps_the_supplied_character_before_action_instructions(self):
        characters=("戴方框眼镜、卷发、蓝围巾的面包人", "左耳黑斑、戴铜铃的白猫")
        for character in characters:
            with self.subTest(character=character):
                result=run("--id","small-paw-wave","--brief","--character",character)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn(character,result.stdout)
                self.assertLess(result.stdout.index(character),result.stdout.index("起势："))
                self.assertIn("[small-paw-wave]",result.stdout)

    def test_character_and_style_are_independent_brief_inputs(self):
        character="额头月牙标记、红围巾的灰色机器人"
        styles=json.loads((SCRIPT.parents[1]/"references"/"styles.json").read_text(encoding="utf-8"))
        styles_by_id={style["id"]:style for style in styles}
        for style_id in ("clay","pixel"):
            with self.subTest(style=style_id):
                result=run("--id","small-paw-wave","--brief","--character",character,
                           "--style",style_id)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn(character,result.stdout)
                self.assertIn(styles_by_id[style_id]["name"],result.stdout)
                self.assertIn("[small-paw-wave]",result.stdout)

    def test_brief_carries_gag_style_and_audience(self):
        text=run("破防了","--brief","--style","clay").stdout
        for piece in ("笑点：崩坏","黏土定格","适用关系","起势","爆点","回环"):
            self.assertIn(piece,text)

    def test_intensity_override_is_noted_in_the_brief(self):
        text=run("--id","small-paw-wave","--brief","--intensity","absurd").stdout
        self.assertIn("强度：抽象",text)
        self.assertIn("原本写的是克制档",text)

    def test_photo_reference_keeps_identity_but_allows_stylization(self):
        text=run("我没事","--brief","--photo-ref").stdout
        self.assertTrue(text.index("身份锚点") < text.index("语气："))
        self.assertIn("面部与发型线索",text)
        self.assertIn("看得出来自本人",text)
        self.assertIn("跨画风、夸张表情、比例变化和形变",text)
        self.assertNotIn("明确选择写实照片",text)

    def test_photo_reference_does_not_replace_a_deforming_gag(self):
        text=run("--id","give-up-rot","--brief","--photo-ref").stdout
        self.assertIn("允许跨画风",text)
        self.assertNotIn("更适合照片的动作",text)
        self.assertNotIn("主体本身不变形",text)

    def test_explicit_photo_style_keeps_texture_and_bold_acting(self):
        text=run("--id","give-up-rot","--brief","--photo-ref","--style","photo-real").stdout
        self.assertIn("明确选择写实照片",text)
        self.assertIn("表情、姿态和动作仍可大胆表演",text)
        self.assertNotIn("默认允许跨画风",text)

    def test_explicit_style_still_wins_over_photo_reference(self):
        text=run("我没事","--brief","--photo-ref","--style","clay").stdout
        self.assertIn("黏土定格",text)
        self.assertNotIn("不得重绘成卡通",text)

    def test_photo_reference_keeps_the_pack_style_available(self):
        text=run("--pack","worker-16","--photo-ref").stdout
        self.assertIn("沙雕手绘",text)
        self.assertIn("默认允许跨画风",text)
        self.assertNotIn("明确选择写实照片",text)
        self.assertIn("角色：沿用参考图主体",text)
        self.assertNotIn("角色：使用原创主体",text)
        self.assertIn("沙雕手绘",run("--pack","worker-16").stdout)

    def test_pack_default_style_is_only_a_candidate(self):
        default=run("--pack","worker-16").stdout
        self.assertIn("候选风格起点（可跨风格组合，不默认整组统一）",default)
        explicit=run("--pack","worker-16","--style","clay").stdout
        self.assertIn("风格：黏土定格",explicit)
        self.assertNotIn("候选风格起点",explicit)

    def test_absurd_brief_allows_hard_cut_without_a_required_rebound(self):
        text=run("破防了","--brief","--intensity","absurd").stdout
        self.assertIn("允许停在结果硬切，不强求回弹",text)
        self.assertNotIn("要有明确的形变和回弹",text)

    def test_only_explicit_photo_style_locks_pack_texture(self):
        self.assertNotIn("明确选择写实照片",run("--pack","worker-16","--photo-ref").stdout)
        text=run("--pack","worker-16","--photo-ref","--style","photo-real").stdout
        self.assertIn("明确选择写实照片",text)
        self.assertIn("表情、姿态和动作仍可大胆表演",text)

    def test_brief_and_pack_always_ask_for_a_playable_gif(self):
        for text in (run("破防了","--brief").stdout,run("--pack","cat-12").stdout):
            self.assertIn("循环动图 GIF",text)
            self.assertIn("只生成一次",text)
            self.assertNotIn("12 帧",text)
            self.assertNotIn("先做前 3 张",text)
            self.assertNotIn("inspect_gif",text)

    def test_reference_identity_failure_is_disclosed_without_auto_retry(self):
        text=run("--id","potato-transform","--brief","--photo-ref").stdout
        self.assertIn("若生成后明显丢失身份，如实说明",text)
        self.assertIn("不自动补抽",text)
        self.assertNotIn("更适合照片的动作",text)

    def test_light_card_names_its_preset(self):
        text=run("--id","okay-bounce-nod","--brief").stdout
        self.assertIn("预设 nod",text)
        self.assertIn("仅供明确要求轻动时",text)

    def test_reply_pack_and_photo_pack_keep_their_promises(self):
        references=SCRIPT.parents[1]/"references"
        cards={c["id"]:c for c in json.loads((references/"actions.json").read_text(encoding="utf-8"))}
        packs={p["id"]:p for p in json.loads((references/"packs.json").read_text(encoding="utf-8"))}
        self.assertEqual({cards[a]["audience"] for a in packs["reply-16"]["actions"]},{"safe"})
        self.assertTrue(all(cards[a]["photo"] for a in packs["photo-12"]["actions"]))

    def test_photoreal_cards_and_pack_do_not_contradict_themselves(self):
        for text in (run("--id","rp-office-sinking","--brief","--photo-ref").stdout,run("--pack","photo-12","--photo-ref").stdout):
            self.assertNotIn("不锁画风",text)
            self.assertIn("明确选择写实照片",text)
        self.assertIn("黏土定格",run("--id","rp-office-sinking","--brief","--photo-ref","--style","clay").stdout)
        self.assertIn("不锁画风",run("--id","smile-while-burning","--brief","--photo-ref").stdout)

    def test_pairs_point_at_each_other_and_say_so_in_the_brief(self):
        cards={c["id"]:c for c in json.loads((SCRIPT.parents[1]/"references"/"actions.json").read_text(encoding="utf-8"))}
        pairs=[c for c in cards.values() if c.get("pair")]
        self.assertGreaterEqual(len(pairs),6)
        for card in pairs:
            partner=cards[card["pair"]["with"]]
            self.assertEqual(partner["pair"]["with"],card["id"])
            self.assertEqual({card["pair"]["step"],partner["pair"]["step"]},{1,2})
        text=run("--id","red-packet-tease-give","--brief").stdout
        self.assertIn("第 1 张",text)
        self.assertIn("red-packet-tease-retract",text)

    def test_holiday_packs_have_seasons_and_the_elder_pack_is_safe(self):
        references=SCRIPT.parents[1]/"references"
        cards={c["id"]:c for c in json.loads((references/"actions.json").read_text(encoding="utf-8"))}
        packs={p["id"]:p for p in json.loads((references/"packs.json").read_text(encoding="utf-8"))}
        for pid in ("christmas-12","newyear-10","spring-elder-12","spring-friends-12"):
            self.assertIn("season",packs[pid])
            self.assertIn("适用时段",run("--pack",pid).stdout)
        self.assertEqual({cards[a]["audience"] for a in packs["spring-elder-12"]["actions"]},{"safe"})
        self.assertIn("适用：",run("--list-packs").stdout)

    def test_zodiac_template_takes_this_years_animal(self):
        text=run("--template","zodiac-greeting","--slot","zodiac=马","--character","戴红围巾的小马").stdout
        self.assertIn("戴红围巾的小马",text)
        self.assertIn("zodiac=马",text)
        self.assertNotEqual(run("--template","zodiac-greeting","--slot","nope=1").returncode,0)

    def test_holiday_phrases_route_to_holiday_cards(self):
        for phrase,expected in {"平安果":"apple-offer","福到了":"fu-upside-down","讨红包":"bowl-for-red-packet",
                                "跨年":"countdown-asleep","立flag":"flag-planted","年夜饭":"dinner-turntable",
                                "亲戚盘问":"relative-triple-question","守岁":"stay-up-toothpick"}.items():
            self.assertEqual(json.loads(run(phrase,"--json","--limit","1").stdout)[0]["id"],expected,phrase)

    def test_unknown_style_is_rejected(self):
        self.assertNotEqual(run("吃瓜","--brief","--style","no-such-style").returncode,0)

    def test_every_pack_renders_in_its_default_style(self):
        packs=json.loads((SCRIPT.parents[1]/"references"/"packs.json").read_text(encoding="utf-8"))
        for pack in packs:
            result=run("--pack",pack["id"],"--character","戴红围巾的饭团")
            self.assertEqual(result.returncode,0,pack["id"])
            self.assertIn("戴红围巾的饭团",result.stdout)
            self.assertEqual(result.stdout.count(" → ")//2,len(pack["actions"]),pack["id"])

    def test_elder_pack_is_all_safe_for_work_groups(self):
        cards={c["id"]:c for c in json.loads((SCRIPT.parents[1]/"references"/"actions.json").read_text(encoding="utf-8"))}
        packs=json.loads((SCRIPT.parents[1]/"references"/"packs.json").read_text(encoding="utf-8"))
        elder=next(p for p in packs if p["id"]=="elder-10")
        self.assertEqual({cards[a]["audience"] for a in elder["actions"]},{"safe"})

if __name__=="__main__":
    unittest.main()
