# 测试文档

## 正常图片

这是一个正常的图片引用：

![Logo](images/logo.png)

## 代码块中的图片语法

下面是代码示例，不应该被提取：

```python
# Python 代码示例
image_syntax = "![example](path.png)"
print("This is code, not real image")
```

```markdown
# Markdown 示例
![code example](code.png)
```

## 另一个正常图片

这个应该被提取：

![Diagram](diagrams/architecture.png)

## 表格示例

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| 1   | 2   | 3   |
