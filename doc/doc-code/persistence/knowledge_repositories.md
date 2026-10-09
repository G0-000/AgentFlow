# persistence/knowledge_repositories.py

> **职责**：读写 `knowledge_docs` 与 `knowledge_chunks`；不负责切分文本、生成 embedding 或计算相似度。

## 一次导入如何落库

```text
KnowledgeService
  → create_doc(title, source) → doc_id
  → chunker 切出片段、embedding 层生成向量
  → add_chunk(doc_id, text, embedding_json)
```

搜索时 `all_chunks()` 读取片段与所属文档标题，由 service 层计算相似度并排序。比如一份 2 页的“值班手册”切成 8 段，repo 存 1 条文档记录和 8 条 chunk；查询“夜间升级联系人”时 repo 返回候选段，service 再按向量相似度排序。

## 读代码时留意

- repo 继承 `BaseRepository`，写入统一走 `_execute`。
- `embedding_json` 以字符串传入；SQLite 的列声明是 `BLOB` affinity，但 Python 实际写入的是 JSON 文本。
- `delete()` 先删 chunks，再删文档，因为当前 schema 没有配置级联删除。
