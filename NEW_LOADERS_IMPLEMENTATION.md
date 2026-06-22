# 新 Loader 实现文档

## 📋 实现概述

本次实现了三个新的文档 Loader：
- ✅ **DocxLoader** - Word 文档 (.docx)
- ✅ **MarkdownLoader** - Markdown 文件 (.md, .markdown)
- ✅ **HtmlLoader** - HTML 文件 (.html, .htm)

所有 Loader 已注册到 LoaderFactory，支持自动格式检测。

---

## 🔧 实现细节

### 1. MarkdownLoader

**文件**: `src/libs/loader/markdown_loader.py`

#### 第三方库

| 库 | 用途 | 选择理由 |
|---|---|---|
| **无** | Markdown 已是目标格式 | 直接读取文本，无需转换 |
| `re` (标准库) | 图片引用提取 | 解析 `![alt](path)` 语法 |

#### 核心功能

1. **文本读取**
   - 直接读取 Markdown 文件（UTF-8 编码，fallback 到 latin-1）
   - 无需格式转换

2. **图片处理**
   - 正则表达式：`!\[([^\]]*)\]\(([^\s\)]+)(?:\s+"[^"]*")?\)`
   - 提取 alt text 和 image path
   - 转换为占位符：`[IMAGE: {image_id}]`
   - 解析相对路径（相对于 Markdown 文件位置）

3. **Title 提取**
   - 优先：第一个 `# Title` 标题
   - 备选：第一个非空行（限制 100 字符）

#### 与 PdfLoader 对齐

| 字段 | PdfLoader | MarkdownLoader | 对齐状态 |
|------|-----------|----------------|----------|
| `Document.id` | `doc_{hash[:16]}` | `doc_{hash[:16]}` | ✅ 完全一致 |
| `Document.text` | Markdown + 占位符 | Markdown + 占位符 | ✅ 完全一致 |
| `metadata.source_path` | 文件路径 | 文件路径 | ✅ 完全一致 |
| `metadata.doc_type` | `"pdf"` | `"markdown"` | ✅ 符合规范 |
| `metadata.doc_hash` | SHA256 | SHA256 | ✅ 完全一致 |
| `metadata.title` | 从标题提取 | 从标题提取 | ✅ 完全一致 |
| `metadata.images[]` | 图片元数据列表 | 图片元数据列表 | ✅ 结构一致 |
| `images[].id` | `{hash}_page_seq` | `{hash}_img_seq` | ✅ 格式一致 |
| `images[].path` | 绝对/相对路径 | 绝对/相对路径 | ✅ 完全一致 |
| `images[].text_offset` | 占位符起始位置 | 占位符起始位置 | ✅ 完全一致 |
| `images[].text_length` | 占位符长度 | 占位符长度 | ✅ 完全一致 |
| `images[].position` | PDF 坐标信息 | 索引信息 | ✅ 结构兼容 |

#### 边界问题

| 问题 | 影响 | 处理方式 |
|------|------|----------|
| **嵌套 Markdown** | 图片语法可能在代码块中 | ⚠️ 当前未处理，会误提取 |
| **URL 图片** | `![](https://...)` | ✅ 保留 URL，不验证可访问性 |
| **相对路径解析** | `![](../images/pic.png)` | ✅ 相对于 Markdown 文件解析 |
| **多语言编码** | 非 UTF-8 文件 | ✅ Fallback 到 latin-1 |
| **损坏的图片语法** | `![alt](path` (缺少括号) | ✅ 正则不匹配，跳过 |

---

### 2. HtmlLoader

**文件**: `src/libs/loader/html_loader.py`

#### 第三方库

| 库 | 用途 | 选择理由 |
|---|---|---|
| **html2text** | HTML → Markdown | 业界标准，输出质量高 |
| **beautifulsoup4** | HTML 解析与清洗 | 强大的 HTML 处理能力 |
| `Pillow` (间接) | 图片处理 | 与 PdfLoader 一致 |

#### 核心功能

1. **HTML 清洗**
   - 移除 `<script>` 标签
   - 移除 `<style>` 标签
   - 移除 HTML 注释
   - 移除 `<noscript>` 标签

2. **Markdown 转换**
   - 使用 html2text 配置：
     ```python
     ignore_links = False      # 保留链接
     ignore_images = True      # 手动处理图片
     body_width = 0            # 不换行
     unicode_snob = True       # Unicode 优先
     skip_internal_links = True # 跳过锚点链接
     ```

3. **图片处理**
   - 提取 `<img>` 标签
   - 获取 `src` 和 `alt` 属性
   - 转换为占位符：`[IMAGE: {image_id}]`
   - 图片追加到文档末尾（html2text 不保留精确位置）

4. **Title 提取**
   - 优先：`<title>` 标签
   - 备选：第一个 `<h1>` 标签

#### 与 PdfLoader 对齐

| 字段 | PdfLoader | HtmlLoader | 对齐状态 |
|------|-----------|------------|----------|
| `Document.id` | `doc_{hash[:16]}` | `doc_{hash[:16]}` | ✅ 完全一致 |
| `Document.text` | Markdown + 占位符 | Markdown + 占位符 | ✅ 完全一致 |
| `metadata.source_path` | 文件路径 | 文件路径 | ✅ 完全一致 |
| `metadata.doc_type` | `"pdf"` | `"html"` | ✅ 符合规范 |
| `metadata.doc_hash` | SHA256 | SHA256 | ✅ 完全一致 |
| `metadata.title` | 从标题提取 | 从 `<title>` 提取 | ✅ 完全一致 |
| `metadata.images[]` | 图片元数据列表 | 图片元数据列表 | ✅ 结构一致 |
| `images[].path` | 本地路径 | 原始 src (可能是 URL) | ⚠️ 可能包含 URL |

**差异说明**：
- HTML 图片的 `path` 字段保留原始 `src` 属性，可能是：
  - 相对路径：`images/pic.png`
  - 绝对路径：`/static/pic.png`
  - URL：`https://example.com/pic.png`
- 这与 PDF 的本地文件路径不同，但符合 HTML 的实际情况

#### 边界问题

| 问题 | 影响 | 处理方式 |
|------|------|----------|
| **复杂 HTML** | 嵌套表格、iframe | ⚠️ html2text 尽力转换，可能丢失结构 |
| **JavaScript 渲染内容** | 动态生成的内容 | ❌ 无法获取（需要浏览器引擎） |
| **Base64 图片** | `<img src="data:image/...">` | ⚠️ 当前未处理，保留原始 src |
| **CSS 样式** | 影响布局的样式 | ✅ 已移除，不影响文本 |
| **损坏的 HTML** | 标签不闭合 | ✅ BeautifulSoup 自动修复 |
| **图片位置** | 精确位置丢失 | ⚠️ 图片追加到末尾 |

---

### 3. DocxLoader

**文件**: `src/libs/loader/docx_loader.py`

#### 第三方库

| 库 | 用途 | 选择理由 |
|---|---|---|
| **mammoth** | DOCX → Markdown | 输出质量优于 python-docx，保留格式 |
| **python-docx** | 元数据提取、图片提取 | 访问 DOCX 内部结构 |
| `Pillow` | 图片处理 | 与 PdfLoader 一致 |

**为什么同时使用两个库？**
- `mammoth`：专注于高质量 Markdown 转换（标题、列表、格式）
- `python-docx`：访问文档属性、图片、关系（mammoth 不提供）

#### 核心功能

1. **Markdown 转换**
   - 使用 mammoth 转换 DOCX → Markdown
   - 保留标题层级、列表、粗体/斜体
   - 记录转换警告

2. **图片提取**
   - 遍历文档关系 (`document.part.rels`)
   - 识别 `image` 类型的关系
   - 提取图片二进制数据
   - 保存到 `data/images/{doc_hash}/`
   - 根据 MIME 类型确定扩展名

3. **元数据提取**
   - Title：优先使用 `core_properties.title`
   - 备选：第一个 Markdown 标题
   - 段落数量：作为"页数"的替代（Word 无固定页）

4. **图片占位符**
   - 转换为：`[IMAGE: {image_id}]`
   - 追加到文档末尾（mammoth 不保留精确位置）

#### 与 PdfLoader 对齐

| 字段 | PdfLoader | DocxLoader | 对齐状态 |
|------|-----------|------------|----------|
| `Document.id` | `doc_{hash[:16]}` | `doc_{hash[:16]}` | ✅ 完全一致 |
| `Document.text` | Markdown + 占位符 | Markdown + 占位符 | ✅ 完全一致 |
| `metadata.source_path` | 文件路径 | 文件路径 | ✅ 完全一致 |
| `metadata.doc_type` | `"pdf"` | `"docx"` | ✅ 符合规范 |
| `metadata.doc_hash` | SHA256 | SHA256 | ✅ 完全一致 |
| `metadata.title` | 从标题提取 | 从属性/标题提取 | ✅ 完全一致 |
| `metadata.images[]` | 图片元数据列表 | 图片元数据列表 | ✅ 结构一致 |
| `images[].path` | 本地路径 | 本地路径 | ✅ 完全一致 |
| `images[].position.page` | 页码 | ❌ 无 | ⚠️ Word 无页码概念 |
| `metadata.paragraph_count` | ❌ 无 | 段落数 | ℹ️ 新增字段 |

**差异说明**：
- Word 文档没有固定页码（取决于打印设置）
- 使用 `paragraph_count` 作为文档长度的指标
- 图片的 `position` 不包含 `page` 字段

#### 边界问题

| 问题 | 影响 | 处理方式 |
|------|------|----------|
| **复杂表格** | 多层嵌套表格 | ⚠️ mammoth 尽力转换，可能丢失格式 |
| **嵌入对象** | Excel 表格、图表 | ❌ 无法提取（仅支持图片） |
| **页眉页脚** | 重复内容 | ⚠️ mammoth 可能包含或忽略 |
| **批注和修订** | Track Changes | ❌ 不提取批注内容 |
| **图片位置** | 精确位置丢失 | ⚠️ 图片追加到末尾 |
| **损坏的 DOCX** | 文件结构错误 | ✅ python-docx 抛出异常 |

---

## 📊 输出对齐总结

### 核心字段对齐表

| 字段 | PDF | DOCX | Markdown | HTML | 状态 |
|------|-----|------|----------|------|------|
| `Document.id` | ✅ | ✅ | ✅ | ✅ | 完全一致 |
| `Document.text` | Markdown | Markdown | Markdown | Markdown | 完全一致 |
| `metadata.source_path` | ✅ | ✅ | ✅ | ✅ | 完全一致 |
| `metadata.doc_type` | `"pdf"` | `"docx"` | `"markdown"` | `"html"` | 符合规范 |
| `metadata.doc_hash` | SHA256 | SHA256 | SHA256 | SHA256 | 完全一致 |
| `metadata.title` | ✅ | ✅ | ✅ | ✅ | 提取逻辑一致 |
| `metadata.images[]` | ✅ | ✅ | ✅ | ✅ | 结构一致 |

### 图片占位符格式

**所有 Loader 统一使用**：
```
[IMAGE: {image_id}]
```

**image_id 格式**：
- PDF: `{doc_hash[:8]}_{page}_{sequence}`
- DOCX: `{doc_hash[:8]}_img_{sequence}`
- Markdown: `{doc_hash[:8]}_img_{sequence}`
- HTML: `{doc_hash[:8]}_img_{sequence}`

### 图片 metadata 结构

**必需字段**（所有 Loader）：
```python
{
    "id": str,              # 唯一标识
    "path": str,            # 图片路径
    "text_offset": int,     # 占位符起始位置
    "text_length": int,     # 占位符长度
    "position": dict        # 位置信息（格式可变）
}
```

**可选字段**：
- `alt_text`: Markdown/HTML 的 alt 属性
- `page`: PDF 的页码
- `width/height`: 图片尺寸

---

## 🔄 Pipeline 集成

### 自动格式检测

```python
# IngestionPipeline.run() 中的代码
loader = LoaderFactory.create_for_file(
    file_path,
    settings=self.settings,
    extract_images=True,
    image_storage_dir=str(resolve_path(f"data/images/{self.collection}"))
)
```

**工作流程**：
1. 提取文件扩展名：`.pdf` / `.docx` / `.md` / `.html`
2. 查找注册表：`_PROVIDERS['pdf']` → `PdfLoader`
3. 实例化 Loader：`PdfLoader(extract_images=True, ...)`
4. 调用 `load()`：返回标准 `Document` 对象

### 后续流程完全复用

```
Document (任何格式)
  ↓
DocumentChunker (切分)
  ↓
Transform Pipeline (增强)
  ↓
Encoding (向量化)
  ↓
Storage (存储)
```

**关键点**：
- ✅ 所有 Loader 输出相同的 `Document` 结构
- ✅ Chunker 只关心 `Document.text` (Markdown)
- ✅ Transform 只关心 `Chunk.text` 和 `metadata`
- ✅ 无需修改任何下游代码

---

## ⚠️ 已知限制与边界问题

### 1. 图片位置精度

| Loader | 位置精度 | 说明 |
|--------|----------|------|
| **PDF** | ✅ 精确 | PyMuPDF 提供页码和坐标 |
| **DOCX** | ❌ 丢失 | mammoth 不保留位置，追加到末尾 |
| **Markdown** | ⚠️ 相对 | 基于文本偏移量，但可能在代码块中误提取 |
| **HTML** | ❌ 丢失 | html2text 不保留位置，追加到末尾 |

**影响**：
- 检索时无法精确定位图片在原文中的位置
- 图片与文本的关联性减弱

**缓解方案**：
- 在 `metadata.images[].position` 中记录原始索引
- 未来可扩展：保留原始文档结构信息

### 2. 复杂格式处理

| 格式 | 问题 | 影响 |
|------|------|------|
| **嵌套表格** | Markdown 表格语法有限 | 可能丢失表格结构 |
| **数学公式** | LaTeX/MathML 转换 | 可能显示为原始代码 |
| **嵌入对象** | Excel、图表 | 无法提取 |
| **动态内容** | JavaScript 渲染 | HTML 无法获取 |

**建议**：
- 对于复杂文档，建议转换为 PDF 后再摄取
- 或使用专门的格式处理工具预处理

### 3. 编码问题

| 问题 | 处理方式 | 状态 |
|------|----------|------|
| **非 UTF-8 文件** | Fallback 到 latin-1 | ✅ 已处理 |
| **损坏的编码** | 记录警告，继续处理 | ✅ 已处理 |
| **特殊字符** | Unicode 优先 | ✅ 已处理 |

### 4. 图片引用问题

| 场景 | Markdown | HTML | 处理方式 |
|------|----------|------|----------|
| **相对路径** | `![](../pic.png)` | `<img src="pic.png">` | ✅ 解析相对路径 |
| **绝对路径** | `![](/images/pic.png)` | `<img src="/pic.png">` | ✅ 保留原样 |
| **URL** | `![](https://...)` | `<img src="https://...">` | ✅ 保留 URL |
| **Base64** | ❌ 不支持 | `<img src="data:...">` | ⚠️ 保留原始 src |
| **不存在的文件** | 路径无效 | 路径无效 | ⚠️ 不验证，记录路径 |

---

## 🧪 测试建议

### 单元测试

**每个 Loader 应测试**：

1. **基本加载**
   ```python
   def test_loader_basic():
       loader = XxxLoader()
       doc = loader.load("test.xxx")
       assert doc.id.startswith("doc_")
       assert doc.metadata["source_path"]
       assert doc.metadata["doc_type"] == "xxx"
   ```

2. **图片提取**
   ```python
   def test_loader_with_images():
       loader = XxxLoader(extract_images=True)
       doc = loader.load("test_with_images.xxx")
       assert "images" in doc.metadata
       assert len(doc.metadata["images"]) > 0
       assert "[IMAGE:" in doc.text
   ```

3. **Title 提取**
   ```python
   def test_loader_title_extraction():
       loader = XxxLoader()
       doc = loader.load("test_with_title.xxx")
       assert "title" in doc.metadata
       assert doc.metadata["title"]
   ```

4. **错误处理**
   ```python
   def test_loader_file_not_found():
       loader = XxxLoader()
       with pytest.raises(FileNotFoundError):
           loader.load("nonexistent.xxx")
   ```

### 集成测试

**Pipeline 集成**：
```python
def test_pipeline_with_xxx_format():
    pipeline = IngestionPipeline(settings, collection="test")
    result = pipeline.run("document.xxx")
    assert result.success
    assert result.chunk_count > 0
```

### 回归测试

**确保 PDF 功能未破坏**：
```python
def test_pdf_still_works():
    pipeline = IngestionPipeline(settings, collection="test")
    result = pipeline.run("document.pdf")
    assert result.success
```

---

## 📦 依赖安装

### 必需依赖

```bash
# PDF (已有)
pip install markitdown pymupdf pillow

# DOCX (新增)
pip install mammoth python-docx pillow

# Markdown (新增)
# 无额外依赖，使用标准库

# HTML (新增)
pip install html2text beautifulsoup4
```

### 完整安装命令

```bash
pip install markitdown pymupdf mammoth python-docx html2text beautifulsoup4 pillow
```

---

## 🎯 使用示例

### 直接使用 Loader

```python
from src.libs.loader import DocxLoader, MarkdownLoader, HtmlLoader

# DOCX
docx_loader = DocxLoader(extract_images=True)
doc = docx_loader.load("report.docx")

# Markdown
md_loader = MarkdownLoader(extract_images=True)
doc = md_loader.load("README.md")

# HTML
html_loader = HtmlLoader(extract_images=True)
doc = html_loader.load("page.html")
```

### 通过 Factory 自动选择

```python
from src.libs.loader import LoaderFactory

# 自动根据扩展名选择
loader = LoaderFactory.create_for_file(
    "document.docx",
    extract_images=True
)
doc = loader.load("document.docx")
```

### Pipeline 自动处理

```python
from src.ingestion.pipeline import IngestionPipeline

pipeline = IngestionPipeline(settings, collection="docs")

# 支持所有格式
pipeline.run("report.pdf")
pipeline.run("guide.docx")
pipeline.run("README.md")
pipeline.run("page.html")
```

---

## ✅ 验证清单

### 功能验证

- [x] DocxLoader 实现完成
- [x] MarkdownLoader 实现完成
- [x] HtmlLoader 实现完成
- [x] 所有 Loader 注册到 Factory
- [x] 支持的扩展名：`pdf, docx, md, markdown, html, htm`
- [x] 输出结构与 PdfLoader 对齐
- [x] 图片占位符格式统一
- [x] 错误处理方式一致

### 架构验证

- [x] 不修改 Pipeline 结构
- [x] 不修改 Chunker 逻辑
- [x] 不修改 Transform 逻辑
- [x] 不修改 Embedding 逻辑
- [x] 完全复用现有流程

### 文档验证

- [x] 实现代码完成
- [x] 第三方库说明
- [x] 输出对齐说明
- [x] 边界问题说明
- [x] 使用示例

---

## 🚀 下一步

### 建议的后续工作

1. **测试编写**
   - 为每个 Loader 编写单元测试
   - 编写 Factory 测试
   - 编写集成测试

2. **文档完善**
   - 添加更多使用示例
   - 补充常见问题 FAQ
   - 编写故障排查指南

3. **功能增强**
   - 支持更多图片格式
   - 改进图片位置精度
   - 支持 Base64 图片
   - 支持嵌套 Markdown 代码块过滤

4. **性能优化**
   - 大文件流式处理
   - 图片提取并行化
   - 缓存机制

---

**文档版本**: v1.0  
**创建日期**: 2024-04-24  
**作者**: Claude Code  
**状态**: ✅ 实现完成
