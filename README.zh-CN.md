# 镜音铃 Codex 宠物 + RinTrace

[![CI](https://github.com/KanadeK/kagamine-rin-codex-pet/actions/workflows/ci.yml/badge.svg)](https://github.com/KanadeK/kagamine-rin-codex-pet/actions/workflows/ci.yml)
[![Pages](https://github.com/KanadeK/kagamine-rin-codex-pet/actions/workflows/pages.yml/badge.svg)](https://kanadek.github.io/kagamine-rin-codex-pet/)
[![Release](https://img.shields.io/github/v/release/KanadeK/kagamine-rin-codex-pet)](https://github.com/KanadeK/kagamine-rin-codex-pet/releases/latest)

**一只完整可运行的镜音铃 Codex v2 宠物，以及一个不公开会话内容也能回放编程过程的隐私安全工具。**

![镜音铃宠物动画总览](media/hero.png)

[English](README.md) ·
[在线演示](https://kanadek.github.io/kagamine-rin-codex-pet/) ·
[下载最新 `.codex-pet`](https://github.com/KanadeK/kagamine-rin-codex-pet/releases/latest)

## 这不是界面空壳

仓库交付的是一条端到端真实功能链：

- 完整 `spriteVersionNumber: 2` 宠物：8×11 图集、192×208 单元格、
  9 种标准动作、16 个顺时针视线方向；
- **RinTrace**：本地读取 Codex JSONL，只保留白名单生命周期元数据，
  丢弃提示词、消息、推理摘要、工具参数/输出、路径和账号值；
- 无网络依赖的 HTML/Canvas 回放舞台，可播放脱敏时间线、预览每种动作、
  测试全部视线方向；
- 严格图集、来源和 SHA-256 校验；
- 写入前双重验证、备份优先的安装/修复、诊断和可恢复卸载；
- 可复现的完整项目 ZIP 与独立 `.codex-pet` 包；
- Python/JavaScript 测试、密钥扫描、CI、Pages、Release 自动化和跨秒
  字节级确定性检查。

## 快速开始

需要 Python 3.11+ 与 Git；Node.js 20+ 只在开发测试时使用。

```bash
git clone https://github.com/KanadeK/kagamine-rin-codex-pet.git
cd kagamine-rin-codex-pet
python -m venv .venv
```

激活环境：

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

验证、试运行、安装和复检：

```bash
python -m pip install -r requirements.txt
python -m rin_pet validate pet --strict --json
python -m rin_pet install --source pet --dry-run --json
python -m rin_pet install --source pet --json
python -m rin_pet doctor --source pet --json
```

默认只写入 `~/.codex/pets/kagamine-rin`，不会修改其他宠物。若已有镜音铃
目录，旧目录会先移动到带 UTC 时间戳的备份，再原子替换。

在 Codex 中打开 **Settings → Appearance → Pets**，或使用 `/pet` 选择自定义
宠物。当前自定义宠物说明见
[Codex 官方手册](https://developers.openai.com/codex/app/features/#pets)。

## 运行真实演示

示例 JSONL 故意包含显眼的 `PRIVATE_*` 消息、路径、工具输入和结果。发布
门禁要求这些值在生成时间线后一个都不能留下。

```bash
python -m rin_pet demo --output dist/demo --json
python -m http.server 8000 --directory dist/demo/site
```

访问 `http://localhost:8000`。舞台只加载本地 HTML、CSS、JavaScript、宠物
图集和脱敏时间线，不依赖统计服务、CDN、网络字体、框架或运行时 API。

处理自己的本地 JSONL：

```bash
python -m rin_pet trace path/to/session.jsonl \
  --output tmp/session-timeline.json --json
python -m rin_pet stage \
  --timeline tmp/session-timeline.json \
  --output tmp/session-stage --json
```

不要提交或上传原始会话。完整边界见
[RinTrace 隐私契约](docs/TRACE_SCHEMA.md)。

## 隐私边界

| 保留 | 丢弃 |
| --- | --- |
| 白名单结构事件类型 | 提示词与消息正文 |
| 动画状态 | 推理摘要 |
| 相对时间与有界时长 | 工具名、参数和输出 |
| 原始行号 | 文件路径与环境值 |
| 输入字节数、记录数、SHA-256 | 账号、邮箱与报错正文 |

未知 `type` 会变成通用 `activity`，不会原样保留。绝对时间会转为相对偏移。
输入上限是 50 MiB / 100,000 条记录，浏览器端还会再次校验输出结构。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `rin-pet validate pet --strict --json` | 校验 v2 拓扑、像素、来源和哈希 |
| `rin-pet trace INPUT --output TIMELINE` | 生成无正文结构时间线 |
| `rin-pet stage --timeline TIMELINE --output SITE` | 构建离线回放舞台 |
| `rin-pet demo --output dist/demo` | 从安全示例构建完整演示 |
| `rin-pet install --source pet --dry-run` | 不写入的安装预演 |
| `rin-pet doctor --source pet` | 诊断安装状态并比对图集 |
| `rin-pet repair --source pet` | 备份后原子修复 |
| `rin-pet uninstall` | 把安装目录移动到备份区 |
| `rin-pet pack` | 生成确定性完整项目 ZIP |
| `rin-pet pack-pet` | 生成确定性独立 `.codex-pet` |
| `rin-pet verify-package FILE --sha256 HASH` | 校验下载文件 |

## 一键验收

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m ruff format --check .
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
node --test tests/js/runtime.test.mjs
python scripts/secret_scan.py --json
python scripts/release_check.py --json
```

最后一条发布门禁还会严格检查 74 个有效单元格（含中性注视帧）和
14 个透明填充单元格，
逐字节重建脱敏示例，构建离线站点，把两种发布包各构建两次并故意间隔超过
一秒，然后比较完整字节、内部时间戳、路径、大小和哈希。它也会拒绝
`Co-authored-by` 提交尾注和未明确允许的脏工作区。

构建并验证发布资产：

```bash
python scripts/build_release.py --version 0.1.0 --output dist --json
python scripts/verify_release.py \
  --artifacts dist \
  --manifest dist/release-manifest.json \
  --checksums dist/SHA256SUMS \
  --json
```

失败时不要直接删除目录，按
[诊断与修复流程](docs/REPAIR.md)处理。

## 架构

```text
Codex JSONL
    │ 本地解析；自由文本全部丢弃
    ▼
脱敏时间线 ───────────────► 离线 Canvas 回放舞台
                                  │
pet.json + 1536×2288 WebP ────────┘
    │
    ├── 严格验证器
    ├── 事务安装 / 诊断 / 修复 / 卸载
    └── 确定性项目 ZIP + 独立 .codex-pet
```

详见[架构说明](docs/ARCHITECTURE.md)、[时间线结构](docs/TRACE_SCHEMA.md)和
[美术/图集流程](docs/ARTWORK.md)。

## 选题为什么是镜音铃

项目初始化前做了本地仓库、现有大型 Codex 宠物索引和 GitHub 仓库/代码
检索。在 2026-07-30 的快照中，171 项索引及定向查询里都没有发现镜音铃
Codex 宠物。她在官方设定中具有适合 192×208 小尺寸的清晰轮廓；Piapro
角色页有数万份相关插画，是来自一方平台的人气信号，不是虚构角色。

完整查询、被排除候选和时效限制见[选题调研](docs/RESEARCH.md)。搜索结果
只能证明当时未发现，未来大版本应重新检查。

## 角色与素材许可

本项目是非官方、非商业同人作品。镜音铃是由 Crypton Future Media, Inc.
管理的 Piapro Character。[PCL 摘要](https://piapro.jp/license/pcl/summary)
明确列出镜音铃并允许制作、公开符合要求的二次创作；最终以
[PCL 正文](https://piapro.jp/license/pcl)和当前
[角色使用指南](https://piapro.jp/license/character_guideline)为准。

> この作品はピアプロ・キャラクター・ライセンスに基づいて
> クリプトン・フューチャー・メディア株式会社のキャラクター
> 「鏡音リン」を描いたものです。

MIT 只覆盖软件与原创文档，不会把角色图像重新许可为 MIT/CC。详见
[ASSET_LICENSE.md](ASSET_LICENSE.md)和[NOTICE.md](NOTICE.md)。仓库不含
官方插画、Logo、音源、歌曲、歌词或游戏素材。

## 安全与贡献

不要把真实 Codex 日志附在公开 Issue 中。路径穿越、压缩包、覆盖、锁和
隐私问题请使用私密漏洞报告，并提供不含私密内容的合成复现。见
[SECURITY.md](SECURITY.md)与[CONTRIBUTING.md](CONTRIBUTING.md)。
