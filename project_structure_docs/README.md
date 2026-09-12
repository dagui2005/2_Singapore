# 项目结构梳理文档 - README

## 文件夹说明

本文件夹用于存放新加坡交通数据项目的结构梳理文档和相关脚本。

## 文件清单

| 文件名 | 说明 |
|--------|------|
| `generate_project_structure_simple.py` | 项目结构分析脚本（简化版，推荐使用） |
| `generate_project_structure.py` | 项目结构分析脚本（完整版，包含emoji） |
| `PROJECT_STRUCTURE.md` | 自动生成的项目结构文档（详细版） |
| `PROJECT_STRUCTURE_SIMPLE.md` | 项目结构文档（简明版，已更新至 v2.0） |
| `README.md` | 本文件 |

## 使用方法

### 1. 重新生成项目结构文档

```bash
# 运行简化版脚本（推荐）
python project_structure_docs/generate_project_structure_simple.py

# 或运行完整版脚本（可能遇到编码问题）
python project_structure_docs/generate_project_structure.py
```

### 2. 查看文档

- **详细版**: `PROJECT_STRUCTURE.md` - 包含完整的文件列表和大小
- **简明版**: `PROJECT_STRUCTURE_SIMPLE.md` - 只包含主要目录和文件说明

## 脚本功能

### generate_project_structure_simple.py

**功能**:
- 自动扫描项目目录结构
- 生成Markdown格式的说明文档
- 统计文件数量和大小
- 按功能分类说明文件用途

**输出**:
- `PROJECT_STRUCTURE.md` - 完整的项目结构文档

## 自定义说明

如果需要添加或修改文件说明，请编辑脚本中的 `load_file_descriptions()` 方法，添加文件路径和说明的映射。

示例:

```python
def load_file_descriptions(self):
    return {
        "README.md": "项目主文档",
        "src/main.py": "主程序入口",
        # 添加更多文件说明...
    }
```

## 维护建议

1. **定期更新** - 当项目结构发生变化时，重新运行脚本
2. **版本控制** - 将生成的文档提交到Git仓库
3. **代码复用** - 将通用的分析脚本提取到此处

## 注意事项

- 脚本会自动跳过 `.git`, `.venv`, `__pycache__` 等目录
- Windows系统下可能遇到编码问题，推荐使用简化版脚本
- 生成的文档使用UTF-8编码

---

**创建时间**: 2026-07-04  
**最后更新**: 2026-07-04（文件整理后更新，新增 scripts/、docs/、reports/ 分类目录）  
**维护者**: AI Assistant
