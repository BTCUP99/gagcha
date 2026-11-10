"""Exercise the public pose-template CLI and reject unusable template data."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/gagcha/scripts/action.py"
SPEC = importlib.util.spec_from_file_location("gif_action_templates", SCRIPT)
ACTION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTION)
TEMPLATES = ACTION.load("motion-templates.json")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8")


class TemplateCliTests(unittest.TestCase):
    def test_list_and_json_expose_reusable_templates(self):
        result = run("--list-templates", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertGreaterEqual(len(rows), 18)
        self.assertIn("snap-freeze", {row["id"] for row in rows})
        self.assertTrue({"paper-slide-exit", "wrap-hide", "clone-pass-blame", "deadpan-overload"}
                        <= {row["id"] for row in rows})
        self.assertIn("瞬间石化", run("--list-templates").stdout)

    def test_template_expands_subject_prop_and_selected_adaptation(self):
        result = run("--template", "peek-retreat", "--character", "短毛橘猫",
                     "--prop", "快递箱", "--subject", "pet", "--style", "crayon")
        self.assertEqual(result.returncode, 0, result.stderr)
        for piece in ("短毛橘猫藏在快递箱后", "主体适配（pet）", "儿童蜡笔", "设计建议", "只生成一次"):
            self.assertIn(piece, result.stdout)
        self.assertNotIn("{subject}", result.stdout)
        self.assertNotIn("主体适配（human）", result.stdout)

    def test_templates_do_not_become_a_fixed_pack(self):
        text = run("--template", "snap-freeze").stdout
        self.assertIn("不是固定组图清单", text)
        self.assertNotIn("9 张", text)
        self.assertNotIn("12 帧", text)
        self.assertNotIn("inspect_gif", text)
        self.assertIn("循环动图 GIF", text)

    def test_selected_variant_is_the_only_expanded_variant(self):
        text = run("--template", "melt-rebound", "--intensity", "absurd").stdout
        self.assertIn("抽象变体", text)
        self.assertNotIn("夸张变体", text)
        text = run("--template", "melt-rebound", "--intensity", "restrained").stdout
        self.assertIn("克制变体", text)
        self.assertNotIn("抽象变体", text)

    def test_template_reference_identity_precedes_the_action(self):
        text = run("--template", "double-take", "--photo-ref").stdout
        self.assertTrue(text.startswith("身份锚点"))
        self.assertIn("面部与发型线索", text)
        self.assertIn("默认允许跨画风", text)
        self.assertIn("不自动补抽", text)
        explicit = run("--template", "double-take", "--photo-ref", "--style", "photo-real").stdout
        self.assertIn("明确选择写实照片", explicit)
        self.assertIn("大胆表演", explicit)
        self.assertNotIn("默认允许跨画风", explicit)

    def test_every_template_can_be_expanded_for_all_supported_body_types(self):
        characters = {"human": "短卷发方眼镜的快递员", "pet": "左耳黑斑的白猫", "object": "带月牙标记的茶壶"}
        prop = "蓝色纸盒"
        for template in TEMPLATES:
            for subject in ("human", "pet", "object"):
                with self.subTest(template=template["id"], subject=subject):
                    character = characters[subject]
                    result = run("--template", template["id"], "--subject", subject,
                                 "--character", character, "--prop", prop)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("主体适配（" + subject + "）", result.stdout)
                    expanded = result.stdout.split("关键姿势：", 1)[1].split("主体适配（", 1)[0]
                    self.assertIn(character, expanded)
                    self.assertIn(prop, expanded)
                    self.assertNotIn("{subject}", expanded)
                    self.assertNotIn("{prop}", expanded)

    def test_single_template_json_and_unknown_template(self):
        result = run("--template", "snap-freeze", "--json")
        self.assertEqual(json.loads(result.stdout)["id"], "snap-freeze")
        missing = run("--template", "does-not-exist")
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("未知姿势模板", missing.stderr)

    def test_check_alias_validates_templates_and_preserves_action_catalog(self):
        result = run("--validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        cards = json.loads((Path(__file__).resolve().parents[1] / "skills" / "gagcha" / "references" / "actions.json").read_text(encoding="utf-8"))
        self.assertIn(f"{len(cards)} 个动作", result.stdout)
        self.assertIn(f"{len(TEMPLATES)} 个姿势模板", result.stdout)


class TemplateValidationTests(unittest.TestCase):
    def test_valid_catalog(self):
        ACTION.validate_templates(TEMPLATES)

    def test_empty_catalog_duplicate_ids_and_non_objects_are_rejected(self):
        for rows in ([], ["wrong"], [TEMPLATES[0], TEMPLATES[0]]):
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    ACTION.validate_templates(rows)

    def test_missing_body_adaptation_and_variant_are_rejected(self):
        for field, missing in (("adaptations", "object"), ("variants", "absurd"),
                               ("slots", "feature")):
            row = copy.deepcopy(TEMPLATES[0])
            del row[field][missing]
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    ACTION.validate_templates([row])

    def test_invalid_pose_placeholders_are_rejected_before_expansion(self):
        for pose in ("{missing}出场", "{subject", "{subject.name}", "{subject!r}"):
            row = copy.deepcopy(TEMPLATES[0])
            row["poses"][0] = pose
            with self.subTest(pose=pose):
                with self.assertRaises(ValueError):
                    ACTION.validate_templates([row])

    def test_timing_must_match_poses_and_be_encodable(self):
        for holds in ([100], [True, 100, 100], [0, 100, 100], [123, 100, 100]):
            row = copy.deepcopy(TEMPLATES[0])
            row["timing"]["holds_ms"] = holds
            with self.subTest(holds=holds):
                with self.assertRaises(ValueError):
                    ACTION.validate_templates([row])
        row = copy.deepcopy(TEMPLATES[0])
        row["timing"]["loop"] = "unknown"
        with self.assertRaises(ValueError):
            ACTION.validate_templates([row])


if __name__ == "__main__":
    unittest.main()
