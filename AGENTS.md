# 代理工作约定

本仓库由 Codex 和 Claude Code 分工维护。在这里工作前先读这一页。

## 分工

- **Codex：** 做图，也可以修改技能文件，比如新增动作、风格、模板或分类。
- **Claude Code：** 审查改动，负责提交、PR、版本号、更新记录和发布。
- **用户：** 决定内容，并在想发布时告诉 Claude Code。

## 不要做这些

除非用户在当前对话里明确要求：

- 不要 `git commit`、`git push`、`git tag`，不要创建 PR 或 Release。
- 不要修改 `skills/gif-actions/SKILL.md` 里的版本号和 `CHANGELOG.md`。

改完把文件留在工作目录里，不用提交，告诉用户改了哪些文件就行。

## 新增内容后

在项目根目录运行：

```sh
python skills/gif-actions/scripts/action.py --check
python tools/build_catalog.py
python -m unittest discover -s tests
```

字段含义和内容要求见 [CONTRIBUTING.md](CONTRIBUTING.md)。`CATALOG.md` 由脚本生成，不要手动修改。

## 文件放哪

- 生成的图和 GIF 放 `output/`，这个目录不会上传。
- 想展示到 README 的样片，告诉用户由 Claude Code 处理，不要自己移进 `examples/`。

## 不要丢掉的规则

修改 `SKILL.md` 时，保留这些规则：内容边界、没说数量时问 6 款还是 9 款、不停在静态图、不要求安装第三方插件。`tests/test_skill_rules.py` 会检查它们。测试失败时修改内容，不要改测试。
