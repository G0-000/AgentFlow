# ============================================================================
# AgentFlow · skills/loader.py —— SKILL.md 发现 / 加载 / 注入
# ============================================================================
# ----------------------------------------------------------------------------
# 📋 【一、基础信息】
# 文件路径: backend/packages/harness/agentflow/skills/loader.py
# 对标来源: evoflow/skills/（loader.py + frontmatter.py + injection.py）
#   原版：技能目录发现、SKILL.md frontmatter 解析、prompt 注入；
#   M3 简化成【扫描目录 → 读 frontmatter → 生成技能列表 prompt】。
# 里程碑: M3
# ----------------------------------------------------------------------------
# 🧩 【二、模块结构图】
# ┌────────────────────────────────────────────────┐
# │ SKILL_DIRS: 默认扫描根（项目根/skills）         │
# │                                                │
# │ parse_skill_md(path) → dict | None             │
# │   读 SKILL.md → 解析 --- 间的 frontmatter      │
# │   （name/description；没有则跳过）              │
# │                                                │
# │ discover_skills(root) → list[dict]             │
# │   递归找 SKILL.md → 逐个解析                   │
# │                                                │
# │ build_skills_prompt(root) → str                │
# │   技能列表 → 提示词段落（无技能 → 空串）        │
# └────────────────────────────────────────────────┘
# ----------------------------------------------------------------------------
# 💡 【三、设计思想】
# 1. SKILL.md 自描述：每个技能一个目录 + 一个说明文件，
#    模型靠 description 知道"什么时候用什么技能"（原版同思想）。
# 2. 无技能目录时返回空串：提示词干净，不引入噪声。
# 3. M3 只做"发现 + 注入说明"；技能内容真正被调用 M6 再学（MCP）。
# ----------------------------------------------------------------------------
# 📤 【四、对外导出 & 内部函数】
# ✅ 对外导出
# 1. discover_skills: 发现全部技能（list[dict]: name/description/path）
# 2. parse_skill_md: 解析单个 SKILL.md
# 3. build_skills_prompt: 技能说明 → 提示词段落
# 🔒 内部私有函数
# 无
# ----------------------------------------------------------------------------
# ⚠️ 【五、修改注意事项 / 风险点】
# 1. frontmatter 解析用极简正则；SKILL.md 格式不规范时跳过（不报错）
# 2. 扫描根可配（CLI 传参）；默认项目根/skills
# 3. 注入内容长度 = 技能数 × description 长度，技能多时注意 token
# ============================================================================

from __future__ import annotations

import re
from pathlib import Path

# 默认技能扫描根（项目根/skills；不存在时 discover 返回空）
DEFAULT_SKILLS_DIR = Path(__file__).resolve().parents[5] / "skills"

# frontmatter: 开头 --- 到下一个 --- 之间的 yaml 块
_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill_md(path: str | Path) -> dict | None:
    """解析一个 SKILL.md：取 frontmatter 的 name/description。

    返回: {"name","description","path"}；格式不规范则返回 None。
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _FM_RE.match(raw)
    if not m:
        return None
    fm = m.group(1)
    name = ""
    desc = ""
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("name:") and not name:
            name = line.split(":", 1)[1].strip().strip('"').strip("'")
        elif line.startswith("description:") and not desc:
            desc = line.split(":", 1)[1].strip().strip('"').strip("'")
    if not name:
        return None
    return {"name": name, "description": desc, "path": str(p)}


def discover_skills(root: str | Path | None = None) -> list[dict]:
    """递归扫描技能根目录，收集全部 SKILL.md 的技能说明。"""
    base = Path(root) if root else DEFAULT_SKILLS_DIR
    if not base.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(base.rglob("SKILL.md")):
        parsed = parse_skill_md(p)
        if parsed:
            out.append(parsed)
    return out


def build_skills_prompt(root: str | Path | None = None) -> str:
    """可用技能 → 提示词段落（无技能返回空串）。"""
    skills = discover_skills(root)
    if not skills:
        return ""
    lines = ["可用技能:", *[f"- {s['name']}: {s['description'] or '（无说明）'}" for s in skills]]
    return "\n".join(lines)
