# 贡献指南

最需要的贡献是能拿去回消息的玩法。先写清楚：对方说了什么，我想表达什么态度，意外发生在哪里。动作卡、模板和风格都应服务于这个意思。

## 默认交付约定

- 新创作没说数量时，先问用户做 6 款还是 9 款，这是开工前唯一的停顿；用户明确指定的数量优先。九宫格是已完成 GIF 的集中预览，不是 9 帧，也不是静态候选。已有成品的改字、调速等局部修改只处理目标数量，本地处理优先；有干净源帧时换字幕不再生成。
- 每款一次生成尝试，跳过锚点图和前三张确认，不做视觉验收。不满意由用户提出，再处理指定款。拿到画面后不自动重抽；工具拒绝、没有产出时不算抽过，改走帧表。失败款如实列出，其余款继续。
- 预览尽量直接排列原 GIF，不要求另做一张合成大 GIF。不要为了截图、评分或报告增加默认生产步骤。
- 参考照片锁定基本特征与轮廓辨识，每次生成实际传入原图。默认允许换画风、颜艺和夸张变形；明确要求写实才锁定媒介，写实也应有表演。
- 模板是可替换角色、道具、语气和风格的动作骨架，不是预先写死的固定菜单。

## 需求与素材的分工

新创作可以组织为“同一句话九演法”“同主体九反应”“同场景九用途”，也可以组合。没有主体的文字允许跨人物、宠物或物件；文字指定主体时保留其特征，明确要求统一角色时整组统一。图片提供辨识约束，图加文字时由文字确定意图和限制。多图角色关系清楚就按需使用，只有关键歧义才询问。用户要求先讨论或确认后制作时暂停生成；明确开始制作并让你自由发挥时，不增加选择确认。完整规则维护在 [requests.md](skills/gagcha/references/requests.md)，不为这些分支另建流程系统。

动作卡负责聊天语义，模板负责姿势骨架，笑点手册负责口语气质与笑点，风格库负责视觉，场景包负责可用回复集合。新素材要补充其负责的能力，避免把某次创作的角色、道具或固定组合写成默认规则。说明与示例使用通用人物、宠物或物件，不复制用户的私人参考图。

## 添加动作

编辑 [actions.json](skills/gagcha/references/actions.json)。同一动作的新叫法放进已有卡片的 `aliases`，能演出不同意思的才新建卡片。

| 字段 | 要求 |
| --- | --- |
| `id` | 稳定的英文短横线 ID，发布后不改 |
| `name` | 中文名，让人一看就有画面 |
| `family` | 类目，见 `scripts/action.py` 的 `FAMILIES` |
| `aliases` | 聊天里真实会说的话 |
| `beat` | 三拍：起势、爆点、收束。写看得见的动作；收束可回环，也可停在结果硬切 |
| `loop` | `reset`、`match`、`pingpong`、`occlusion`、`cycle`、`hold`，含义见 [action.py](skills/gagcha/scripts/action.py) 的 `LOOPS` |
| `subjects` | `human`、`mascot`、`pet`、`object`、`text` |
| `mood`、`camera` | 语气和机位 |
| `gag` | 笑点机制，见[笑点手册](skills/gagcha/references/comedy.md) |
| `intensity` | `restrained`、`exaggerated`、`absurd` |
| `audience` | `safe`、`casual`、`close` |
| `motion` | `action`（动作变化，可用关键姿势粗跳、停顿和硬切）或 `light`（一个姿势就能读懂，同时要写 `preset`） |
| `photo` | 兼容旧字段，表示能否按自然身体比例实拍；供可选 `--photo-ok` 筛选使用，不是人物参考图的准入条件，也不限定画风 |

`cycle` 只用于同方向连续运动，比如转圈。手回到原位属于 `reset`。

## 添加动作模板

编辑 [motion-templates.json](skills/gagcha/references/motion-templates.json)。模板只描述可以复用的动作结构，把角色身份、道具和局部细节留作槽位；同一个模板应能演出不止一种意思。

| 字段 | 要求 |
| --- | --- |
| `id`、`name` | 稳定 ID 与容易理解的动作名称 |
| `intents` | 适用的聊天意图，字符串列表 |
| `poses` | 按顺序写关键姿势，突出准备、爆点与收束；不要求补齐平滑过渡 |
| `slots` | 角色、道具、识别特征等可替换项，以字典描述 |
| `variants` | 能改变语气或笑点的变化，不只替换颜色 |
| `adaptations` | 不同主体的演法，避免把人的手脚机械套到宠物或物件上 |
| `timing` | 各关键姿势的 `holds_ms`、`loop` 和节奏说明 `note` |

用 `python skills/gagcha/scripts/action.py --list-templates` 查看列表，用 `--template snap-freeze` 展开。新增模板后运行 `--check` 与图鉴生成脚本。不要为了收录一个模板先批量生成媒体。

## 添加风格、表情包和热梗

- **风格**（[styles.json](skills/gagcha/references/styles.json)）：写可执行的视觉描述和要避免的问题，不写艺术家或 IP 的名字。可以粗糙、丑萌、抠图、混搭；不要把精致或统一材质当作唯一目标。
- **表情包**（[packs.json](skills/gagcha/references/packs.json)）：列出候选动作 ID 和默认风格。动作之间要有足够差异；包内候选数量不覆盖用户本次要求或默认交付数量。
- **热梗**（[trends.json](skills/gagcha/references/trends.json)）：写说法、释义、对应动作和收录日期。过气的梗可以提交删除。

## 内容边界

- 不收录真实名人的形象、声音或标志性片段，也不复制现成 IP。可以收录能演出来的情绪和说法。
- 不收录粗口、色情内容，不收录针对具体人或群体的攻击。
- 只提交自己创作、有权开源的文字和图片。

## 使用依据

没有依据的动作标为“创作提案”，这样完全没问题。如果有公开使用依据，在 [evidence.json](skills/gagcha/references/evidence.json) 里按 ID 关联来源。不要写“最流行”这类无法核实的说法。

## 提交前检查

在项目根目录运行：

```sh
python skills/gagcha/scripts/action.py --check
python tools/build_catalog.py
python -m unittest discover -s tests
python tools/benchmark.py   # 查看命中率和未命中的词
```

`CATALOG.md` 由脚本生成，不要手动修改。持续集成会检查它是否最新，并运行以上测试。这些是代码与数据贡献的检查，不是要求每次制作 GIF 都运行测试、生成联系表或反复返修。

## 维护分工

本项目用 Codex 做图和扩充内容，用 Claude Code 审查和发布，具体约定见 [AGENTS.md](AGENTS.md)。外部贡献者直接提 PR 即可。

## 本地开发与同步

把技能链接到工作目录，改动立刻生效，不用反复安装：

```sh
git clone https://github.com/BTCUP99/gagcha.git
cd gagcha
python -m pip install -r skills/gagcha/requirements.txt
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/gagcha" ~/.agents/skills/gagcha
```

`ln -s` 只需运行一次，之后 Codex 用的就是这个目录当前的内容，包括还没提交的改动。改完开一个新的 Codex 会话，就能用上新版本。

**拉取公开仓库的最新内容：**

```sh
git switch main
git pull --ff-only
```

`--ff-only` 只接受能直接前进的更新。如果它报错，说明本地 `main` 有没推送的提交，先处理好，不要强行覆盖。

**改动和提交：**

```sh
git switch -c fix/简短说明
# 修改、测试、提交
git push -u origin HEAD
gh pr create --fill
gh pr merge --squash --delete-branch   # CI 通过后合并
git switch main && git pull --ff-only
```

`main` 必须走 PR 且 CI 通过才能合并，禁止强制推送和删除；`v*` 标签禁止修改和删除。不设人工审批。

## 版本与发布

版本号遵循语义化版本：修 bug 升第三位，新增玩法或工具升第二位。日常改动先记在 [CHANGELOG.md](CHANGELOG.md) 的 `[Unreleased]` 下，不是每次合并都要发版。

发版时：

1. 把 `[Unreleased]` 改成版本号和日期，并同步 `skills/gagcha/SKILL.md` 里的 `version`，走 PR 合入 `main`。
2. 打标签并推送：

   ```sh
   git switch main && git pull --ff-only
   git tag -a v1.0.2 -m "Gagcha 1.0.2"
   git push origin v1.0.2
   ```

推送标签后，[Release 工作流](.github/workflows/release.yml) 会跑测试、核对版本号、打包技能目录，并用更新记录的对应章节发布 GitHub Release。压缩包不提交进仓库。
