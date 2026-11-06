"""Guard the skill rules that a rewrite could silently drop; the model only follows what the text says."""
from pathlib import Path
import unittest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "gagcha"


def skill_text():
    return "\n".join(path.read_text(encoding="utf-8") for path in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))])


class SkillRuleTests(unittest.TestCase):
    def test_content_boundaries_stay_in_the_skill(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for word in ("公众人物", "现成 IP", "有权使用", "羞辱", "性化", "粗口", "未成年"):
            self.assertIn(word, text, word)

    def test_it_asks_for_six_or_nine_only_when_no_quantity_was_given(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("做 6 款还是 9 款", text)
        self.assertIn("已说数量", text)
        self.assertNotIn("默认九款", skill_text())

    def test_a_still_image_or_a_refusal_falls_back_to_the_sheet_route(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for phrase in ("不要停在 PNG", "第三方插件", "请求被拒绝"):
            self.assertIn(phrase, text, phrase)

    def test_the_skill_never_mentions_the_api_route(self):
        text = skill_text()
        for word in ("generate_gif", "GIF_ACTIONS_API", "OPENAI_API_KEY", "allow-paid"):
            self.assertNotIn(word, text, word)
        self.assertFalse((SKILL / "scripts" / "generate_gif.py").exists())

    def test_skill_version_matches_the_latest_changelog_release(self):
        import re
        root = SKILL.parents[1]
        skill = re.search(r"^  version: (\S+)$", (SKILL / "SKILL.md").read_text(encoding="utf-8"), re.M).group(1)
        changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        released = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M).group(1)
        self.assertEqual(skill, released)

    def test_tests_are_not_shipped_in_the_skill_package(self):
        self.assertEqual(list(SKILL.rglob("test_*.py")), [])

    def test_release_notes_pick_only_the_requested_version(self):
        import sys
        sys.path.insert(0, str(SKILL.parents[1] / "tools"))
        import release_notes
        text = "## [Unreleased]\n\n- a\n\n## [0.2.0] - x\n\n- b\n\n## 0.1.0\n\n- c\n\n[0.2.0]: https://e\n"
        self.assertEqual(release_notes.notes("0.2.0", text), "- b")
        with self.assertRaises(ValueError):
            release_notes.notes("9.9.9", text)
        self.assertIn("首个正式版本", release_notes.notes("1.0.0"))

    def test_every_script_the_docs_name_exists(self):
        import re
        for name in set(re.findall(r"scripts/([a-z_]+\.py)", skill_text())):
            self.assertTrue((SKILL / "scripts" / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
