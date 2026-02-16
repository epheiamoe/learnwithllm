# AGENTS.md

## 项目快速概览

AI Learning Assistant 是一个个人智能导师Web应用，通过结构化上下文管理实现长程教学。

**技术栈**: Python 3.8+ + Flask + HTML5/CSS3/ES6 + OpenAI API

**核心机制**:

- 上下文分层：启动询问阶段与正式教学阶段完全隔离
- KV Cache优化：固定前缀提示词结构，最大化推理加速
- 工具系统：LLM可随时调用工具（出题/搜索/文件操作）

## 必须遵守的代码风格

### Python

- 使用类型注解（typing模块）
- 函数和类必须有docstring
- 使用双引号字符串（除非字符串内有双引号）
- 日志记录使用logging模块，禁止print

### JavaScript

- 使用ES6+语法（const/let、箭头函数、async/await）
- 使用严格相等（=== 和 !==）
- 事件监听器使用addEventListener，避免内联onxxx
- DOM操作前检查元素存在性

### CSS

- 使用CSS变量（定义在:root）
- 类名使用kebab-case
- 响应式断点：1024px、768px、480px
- 深色模式使用[data-theme="dark"]选择器

### HTML

- 使用语义化标签
- 图片必须有alt属性
- 表单元素必须有label

## 常用命令速查

```bash
# 安装依赖
pip install -r requirements.txt

# 配置（首次运行）
python setup.py

# 开发模式启动
python app.py

# 生产模式启动（使用gunicorn）
gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app

# 查看日志
tail -f debug.log
```

## 项目结构速查

```
ai-learning-assistant/
├── app.py              # Flask主应用（路由、LLM调用、工具执行）
├── setup.py            # 交互式配置向导
├── config.yml          # 配置文件
├── static/             # 静态文件
│   ├── css/style.css   # 全局样式
│   └── js/main.js      # 共享JavaScript
├── templates/          # HTML模板
│   ├── base.html       # 基础模板
│   ├── index.html      # 首页
│   └── chat.html       # 对话页面
└── workspaces/         # 工作区目录（运行时创建）
```

## 关键架构约束

### 阶段隔离（重要！）

- **需求询问阶段** (`/api/workspaces/<id>/inquiry`): 
  
  - 使用`PHASE1_INQUIRY_PROMPT`
  - **禁止提供任何工具**
  - 仅收集学习需求

- **正式教学阶段** (`/api/workspaces/<id>/chat`):
  
  - 使用`PHASE2_TEACHING_PROMPT`
  - 提供完整工具集
  - 需要`study_plan.md`存在

### 上下文管理

- 固定前缀结构用于KV Cache优化
- Token超过80%阈值时自动压缩
- 保留最近10轮对话原文

### 工具调用

- 工具使用 **OpenAI Function Calling** 标准机制
- 工具通过 API 自动调用，**严禁在提示词中给出任何手动格式示例**（如 XML、DSML、JSON 格式）
- 提示词只需说明工具功能和参数，不要给出"调用示例"
- 工具定义只在正式教学阶段传入LLM
- 模型只需正常对话表达意图，系统会自动处理工具调用
- 工具执行结果不保存到对话历史

## 修改指南

### 添加新工具

1. 在`ToolExecutor`类中添加方法（参考现有工具）
2. 在`PHASE2_TEACHING_PROMPT`的[AVAILABLE_TOOLS]部分添加说明
3. 在`teaching_chat`路由的tools列表中添加JSON Schema定义
4. 前端`chat.html`中添加工具状态显示（可选）

### 修改提示词

- 所有提示词统一在 `prompts.yml` 中配置
- 询问阶段：修改 `phase1_inquiry.system`
- 教学阶段：修改 `phase3_teaching.system`
- **重要**：不要在提示词中给出任何工具调用的格式示例（如`工具: xxx`、`参数: xxx`等），系统使用 OpenAI Function Calling 自动处理

### 修改前端样式

- 全局样式：`static/css/style.css`
- 变量定义在`:root`和`[data-theme="dark"]`
- 响应式设计在@media查询中

### 修改页面逻辑

- 首页：`templates/index.html`
- 对话页：`templates/chat.html`（内联JavaScript）
- 共享工具：`static/js/main.js`

## 安全 & 禁区

- **永远不要把API密钥写死在代码里** - 使用config.yml
- **不要直接操作数据库** - 使用WorkspaceManager提供的接口
- **不要在工作区目录外读写文件** - 使用file_system工具的路径验证
- **不要在生产环境开启FLASK_DEBUG**

## 调试技巧

### 查看LLM请求

```python
# 在app.py中添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 查看工作区数据

```bash
# 查看工作区列表
ls workspaces/

# 查看对话历史
cat workspaces/xxx/history.json | python -m json.tool

# 查看学习计划
cat workspaces/xxx/study_plan.md
```

### 测试LLM连接

```bash
python setup.py
# 选择选项5: 测试LLM连接
```

# 

## 依赖版本

```
flask>=2.3.0
pyyaml>=6.0
requests>=2.31.0
markdown>=3.5.0
python-dotenv>=1.0.0
```

## 参考文档

- Flask: https://flask.palletsprojects.com/
- OpenAI API: https://platform.openai.com/docs/
- SSE (Server-Sent Events): https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
