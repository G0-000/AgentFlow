#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AgentFlow doc-code 生成器：为每个 py 文件生成独立说明文档。

- 目录结构与代码目录一致（doc-code/ 镜像 agentflow/）
- 信息源：每个 py 文件的头部注释（结构图/设计思想/风险）+ 顶层符号
- 附加：实用场景（按文件定制或分类映射）+ 涉及问题
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path("/Users/main/AgentFlow/backend/packages/harness/agentflow")
DST = Path("/Users/main/AgentFlow/doc/doc-code")

# 场景映射：文件名关键词 → 定制场景；否则按目录分类
SPECIAL_SCENES = {
    "tool_result_store.py": [
        "对话流只显摘要：工具返回大结果（网页/文件/搜索）时，聊天里只展示截断摘要，避免刷屏与上下文爆炸",
        "追问引用完整结果：用户问\"刚才那个网页具体内容\"，Agent 按 thread_id+tool_call_id 取回原文",
        "调试审计：summaries(thread_id) 列出某会话全部工具调用摘要，排查\"工具当时返回了什么\"",
        "UI 工具卡片（M7）：gateway 返回工具调用记录、前端渲染工具卡片时读 name+summary",
        "多会话隔离：thread 维度键设计，进程内多会话并行不串扰",
    ],
    "tools.py": [
        "Agent 启动装配：get_available_tools() 输出最终挂载给 Agent 的工具列表（CLI/未来 gateway 共用）",
        "工具开发回归：新增工具后测试去重与 tier 排序是否生效",
        "性能敏感场景：lru_cache 延迟加载避免启动时 import 全部工具模块（requests 等重依赖）",
        "原版对齐演示：对照 EvoFlow 原版 tools.py（566 行）理解\"收集-去重-排序\"管线",
    ],
    "tool_catalog.py": [
        "工具分层展示：gateway 返回工具列表时附带 tier 与中文标签（enrich_tool_catalog_fields）",
        "工具排序：tier_sort_key 供 tools.py 按\"系统核心→常驻→工作区\"排序",
        "新增工具登记：TOOL_TIER_MAP 追加一行即可定义新工具的档位（不登记默认 optional）",
        "DB 同步/UI 过滤（原版用途）：后续按 tier 做会话工具勾选、退役工具隐藏",
    ],
    "clarification_tool.py": [
        "意图不明确时澄清：Agent 判断用户需求模糊 → return_direct=True 直接反问用户",
        "会话脊柱工具：与原版 SESSION_SYSTEM_TOOL_NAMES 对齐，属于 runtime 档系统核心",
        "工具模板学习：39 行最小工具模板（docstring 即说明书），新工具开发的起点",
    ],
    "todo_tool.py": [
        "会话内待办：对话中\"帮我记个待办\"，Agent 自动调 add（实测：已添加待办: 学完M2（todo-1））",
        "任务跟进：list/update/delete 支撑对话中管理待办清单",
        "M2 验收演示：工具自动调用链路的默认测试工具",
    ],
    "knowledge_tool.py": [
        "知识库检索（M5 接入前占位）：search/read/list 接口先行，_format_hit 统一命中格式",
        "接口契约先行：工具名称/参数/返回格式固定，后续换向量库实现不动调用方",
    ],
    "plan_tool.py": [
        "会话内计划：get/update/save 管理对话中的计划（如学习计划分步）",
        "计划持久化后续：M2 内存版，M3+ 可落 SQLite 或文件",
    ],
    "fetch_url_tool.py": [
        "网页内容获取：用户给 URL 问内容 → 工具抓取并粗清洗（2000 字上限）",
        "静态页面场景：README/文档页/新闻页等可直接抓取文本",
        "注意：动态渲染页面（JS）抓不到正文，需 M5+ 浏览器工具",
    ],
    "title_middleware.py": [
        "会话列表显示：首条消息自动生成标题（截断 20 字），sessions.title 落库后列表可读",
        "免 LLM 稳定方案：规则截断不调模型，避开免费模型高峰限流（P-015）",
        "换 LLM 生成：后续想升级为智能标题只改 _generate_title 内部实现",
    ],
    "thread_data_middleware.py": [
        "会话工作区隔离：每个 thread 独立 user-data/{workspace,uploads,outputs}",
        "M3 文件工具的地盘：文件读写工具的输出落这里，会话间不串扰",
        "上传/输出目录规划：uploads 收用户上传，outputs 放 Agent 生成物",
    ],
    "app_config.py": [
        "全局配置入口：CLI/未来 gateway 统一从 config.yaml 加载配置",
        "配置缺失检测：models 段未配/无 API key 时给出明确提示（CLI 启动检查）",
        "多环境切换：改 config.yaml 即可切模型/供应商/数据路径",
    ],
    "model_config.py": [
        "模型配置数据结构：chat 模型/provider/base_url/api_key 的字段定义",
        "环境变量展开：api_key 支持 ${ENV} 从 .env 读取，密钥不落 yaml",
    ],
    "models_yaml.py": [
        "YAML 加载与校验：config.yaml → 结构化配置（models 段）",
        "多 provider 支持：zhipu/deepseek/openai 兼容 OpenAI 协议",
    ],
    "paths.py": [
        "路径解析唯一入口：项目根/data 目录/默认 DB 路径集中管理",
        "消除 cwd 依赖：不依赖\"从哪个目录启动\"（P-014 教训）",
    ],
    "factory.py": [
        "模型工厂：按配置创建 ChatOpenAI（zhipu/deepseek 都是 OpenAI 兼容协议）",
        "切模型只需改配置：4.5↔4.7↔DeepSeek 不用改代码（config.yaml 注释里有备选）",
        "测试注入点：测试可传 mock 模型，不真调 API",
    ],
    "patched_openai.py": [
        "智谱流式修复：extra_body thinking disabled，让流式走 content 而非 reasoning_content（P-016）",
    ],
    "bootstrap.py": [
        "启动建表：sessions/session_messages + checkpoint 表，幂等（已存在跳过）",
        "测试便利：init_db(\":memory:\") 内存库跑测试",
    ],
    "db.py": [
        "数据库连接管理：SQLite 连接创建/复用",
    ],
    "schema.py": [
        "表结构定义：sessions/session_messages 字段的唯一权威来源",
    ],
    "repositories.py": [
        "检查点/业务表 SQL 的底层封装（原版分层思想）",
    ],
    "session_repositories.py": [
        "会话业务记录：create/get/delete/touch/update_title",
        "消息记录：add_message/list_messages（明文，与检查点二进制互补）",
        "CLI 标题落库：update_title 写 sessions.title",
    ],
    "timestamps.py": [
        "统一时间戳：ISO 格式 + UTC，避免各文件各写各的",
    ],
    "agent.py": [
        "主 Agent 构建：make_lead_agent 装配模型+检查点+工具+中间件",
        "会话持久化：create_agent checkpointer 参数让每步状态落 SQLite",
        "M2 扩展点：tools/middlewares 参数挂工具目录与横向能力",
    ],
    "prompt.py": [
        "系统提示词构建：时间注入（Agent 知道\"今天\"，不必调工具，P-011）",
        "提示词集中管理：不散在调用处，改提示词只改这一处",
    ],
    "provider.py": [
        "SQLite 检查点工厂：SqliteSaver 连接封装（thread_id 维度持久化）",
    ],
    "async_provider.py": [
        "异步检查点：AsyncSqliteSaver（未来 gateway 异步场景用）",
    ],
    "thread_state.py": [
        "自定义图状态：AgentState 子类，为后续复杂状态预留",
    ],
    "main.py": [
        "终端对话入口：uv run agentflow",
        "完整装配演示：config→db→checkpointer→tools→middlewares→model→agent→循环",
        "流式输出：langgraph stream 逐块打印（P-016 嵌套结构兼容）",
        "自动标题落库：首轮后 get_state 读 title → sessions.update_title",
        "启动信息：模型/工具/会话/数据一目了然（用户明确要求）",
        "调试与演示：无 Web UI 前的最快验证路径",
    ],
}

# 目录级兜底场景
DIR_SCENES = {
    "config": ["配置文件修改与校验场景：改模型/provider/路径后重跑 CLI 生效", "多环境（开发/生产）切换配置的单一入口"],
    "models": ["切换模型供应商场景：zhipu↔deepseek↔openai 兼容协议，改配置即切", "测试 mock 场景：不真调 API 也能验证装配逻辑"],
    "persistence": ["数据落库与恢复场景：重启进程后会话/消息仍在", "会话隔离场景：多个 thread_id 互不干扰", "数据库迁移场景：改 schema.py 后重跑 bootstrap 幂等建表"],
    "agents": ["Agent 装配与扩展场景：加工具/加中间件/换模型都在这里接线", "会话恢复场景：--thread 复用历史上下文"],
    "tools": ["Agent 能力扩展场景：新增工具模块后自动被收集挂载", "工具结果管理场景：摘要与完整结果分离，控制上下文成本"],
    "cli": ["终端调试场景：不依赖 Web UI 快速验证功能", "自动化测试场景：管道输入 exit 可脚本化验收"],
}

Q_A = {
    "tools.py": [("为什么延迟加载？", "5 个工具模块含 requests 等重依赖，模块级 import 拖慢 CLI 启动；lru_cache 保证只加载一次，之后复用"),
                 ("lru_cache 怎么清？", "修改工具定义后需重启进程（或手动 cache_clear）；调试期重启最省事")],
    "tool_catalog.py": [("tier 排序谁在用？", "tools.py 的 _finalize_tool_catalog；CLI 启动信息里按 tier 顺序列工具"),
                        ("新增工具不登记会怎样？", "resolve_tool_tier 兜底 optional，会排到工具列表最后，但不报错")],
    "tool_result_store.py": [("为什么摘要和原文分开存？", "对话流 token 成本：只放摘要进上下文；原文按需取回，不重新调工具"),
                             ("内存版会丢数据吗？", "进程重启即丢；M3+ 跨进程场景落 SQLite 即可")],
    "title_middleware.py": [("为什么不用 LLM 生成标题？", "免费模型高峰限流（P-015）会让标题生成挂掉、拖慢首轮对话；规则截断 100% 稳定"),
                            ("标题会重复生成吗？", "不会——已有 title 时 before_model 直接返回 None，幂等")],
    "thread_data_middleware.py": [("目录在哪？", "data/threads/{thread_id}/user-data/{workspace,uploads,outputs}"),
                                  ("为什么 eager 建目录？", "M2 简化：一次建好；原版 lazy 按需创建，M3 文件工具可改回")],
    "session_repositories.py": [("和检查点（checkpointer）什么关系？", "检查点存图状态二进制（恢复对话用）；session_repositories 存业务明文（列表展示用），两者互补"),
                                ("消息存明文安全吗？", "本地单机调试够用；M7 gateway 上线前需考虑脱敏")],
    "factory.py": [("zhipu/deepseek 为什么都能用？", "都是 OpenAI 兼容协议，ChatOpenAI 换 base_url+api_key 即可"),
                   ("怎么切回 DeepSeek？", "config.yaml models 段 provider 改 deepseek，.env 配 DEEPSEEK_API_KEY")],
    "main.py": [("为什么启动信息要显示模型？", "P-014/015/016 调试全靠它——限流/流式问题第一时间看到是哪个模型/供应商"),
                ("--thread 怎么用？", "启动时打印的会话 ID 加 --thread 可继续上次对话（持久化验证入口）")],
    "app_config.py": [("配置加载失败会怎样？", "CLI 提示\"缺少模型配置\"并退出，不会带着坏配置跑")],
}

# 无实用场景可写的纯占位包
SKIP_DETAIL = {"__init__.py"}


def extract_header(text: str) -> tuple[str, str, str, str]:
    """提取头部注释：title_line / 结构图块 / 设计思想段 / 风险段。

    只取文件开头到第一个 import/from 之前的 # 行；剥掉行首 # 前缀；滤掉分割线。
    """
    lines = text.splitlines()
    # 切出头部注释区（# 开头且尚未遇到 import）
    header: list[str] = []
    for ln in lines[:80]:
        if ln.lstrip().startswith(("from __future__", "import ", "from ")):
            break
        if ln.startswith("#"):
            header.append(ln)
        elif not ln.strip():
            continue
        else:
            break

    def clean(l: str) -> str:
        s = re.sub(r"^#\s?", "", l)
        s = s.rstrip()
        return s

    title_line = ""
    diagram_lines: list[str] = []
    design_lines: list[str] = []
    risk_lines: list[str] = []
    mode = ""
    for raw in header:
        ln = clean(raw)
        if ln.startswith("AgentFlow"):
            title_line = ln
        if "┌" in ln:
            mode = "diagram"
            diagram_lines.append(ln)
            continue
        if mode == "diagram":
            diagram_lines.append(ln)
            if "┘" in ln:
                mode = ""
            continue
        if "【三、设计思想】" in ln or "为什么这样设计" in ln:
            mode = "design"
            continue
        if "【四、对外导出" in ln or "【五、修改注意事项" in ln:
            mode = "risk" if "【五" in ln else ""
            continue
        if mode == "design":
            if ln.strip().startswith(("📤", "🧩", "📋", "⚠️", "💡")):
                continue
            if set(ln.strip()) <= {"-", "="}:
                continue
            design_lines.append(ln)
        if mode == "risk":
            if ln.strip().startswith(("📋", "🧩", "💡", "📤", "⚠️")):
                continue
            if set(ln.strip()) <= {"-", "="}:
                continue
            risk_lines.append(ln)
    # 结构图同样剥前缀（保留框线；排除纯分割线）
    diagram = "\n".join(
        l for l in diagram_lines if (set(l.strip()) - {"#", "-", "="})
    )
    return title_line, diagram, "\n".join(design_lines[:14]), "\n".join(risk_lines[:10])


def top_symbols(text: str) -> tuple[list[str], list[str], list[str]]:
    """AST 提取顶层 def / class / 常量。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], [], []
    funcs, classes, consts = [], [], []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    consts.append(t.id)
    return funcs, classes, consts


def main() -> None:
    generated = []
    for py in sorted(SRC.rglob("*.py")):
        rel = py.relative_to(SRC)
        name = py.name
        text = py.read_text(encoding="utf-8")
        title_line, diagram, design, risk = extract_header(text)
        funcs, classes, consts = top_symbols(text)

        md_path = DST / rel.with_suffix(".md")
        md_path.parent.mkdir(parents=True, exist_ok=True)

        # 场景
        scenes = SPECIAL_SCENES.get(name)
        if not scenes:
            for k in DIR_SCENES:
                if rel.parts[0] == k:
                    scenes = DIR_SCENES[k]
                    break
        if scenes is None:
            scenes = ["（待补充具体场景）"]

        # Q&A
        qa = Q_A.get(name, [])

        # 职责描述：标题行去 # 前缀
        duty = title_line.replace("# AgentFlow · ", "").split("——", 1)[-1].strip() if title_line else "（无头部标题）"
        rel_parts = " → ".join(rel.parts)

        md = f"""# {rel} — {name}

> **文件路径**: `backend/packages/harness/agentflow/{rel}`
> **目录位置**: {rel_parts}
> **职责**: {duty}

## 📋 结构图

```text
{diagram if diagram else "（无复杂调用图）"}
```

## 📤 关键导出

"""
        if classes:
            md += "**类**\n\n" + "\n".join(f"- `{c}`" for c in classes) + "\n\n"
        if funcs:
            md += "**函数**\n\n" + "\n".join(f"- `{f}()`" for f in funcs) + "\n\n"
        if consts:
            md += "**常量**\n\n" + "\n".join(f"- `{c}`" for c in consts) + "\n\n"
        if not (classes or funcs or consts):
            md += "（无顶层导出，见结构图）\n\n"

        md += "## 💡 设计思想\n\n" + (design if design else "（无，见代码内注释）") + "\n\n"
        md += "## 🎯 实用场景\n\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(scenes, 1)) + "\n\n"

        if qa:
            md += "## ❓ Q&A\n\n"
            for q, a in qa:
                md += f"**Q: {q}**\n\nA: {a}\n\n"

        if risk:
            md += "## ⚠️ 风险点\n\n" + risk + "\n\n"

        md += "---\n"
        md += f"_自动生成于 doc-code 规范落地（2026-09-28）。来源：{name} 头部注释 + 顶层符号。_\n"
        md_path.write_text(md, encoding="utf-8")
        generated.append(str(rel))

    print(f"生成 {len(generated)} 个文件说明")
    for g in generated:
        print(" ", g)


if __name__ == "__main__":
    main()
