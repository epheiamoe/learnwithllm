# AI Learning Assistant

AI协作学习助手 - 基于结构化上下文管理的个人智能导师

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## 功能特性

- **两阶段学习流程**:
  - **需求询问阶段**: AI只提问收集信息，不提供教学
  - **正式教学阶段**: 基于个性化学习计划进行系统教学
- **上下文感知**: 智能上下文压缩与分层管理，确保长程教学中知识连贯不丢失
- **结构化学习**: AI自动生成学习计划，循序渐进掌握知识点
- **实时搜索**: 集成多种搜索引擎，获取最新知识
- **智能练习**: 多种题型自动生成，客观题即时反馈，主观题AI批改
- **深色/浅色模式**: 支持主题切换，保护视力
- **响应式设计**: 完美适配桌面和移动设备
- **本地持久化**: 所有数据保存在本地，隐私安全

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

首次运行需要配置LLM和搜索服务：

```bash
python setup.py
```

按照向导提示配置：
- LLM提供商（OpenAI、Google、Kimi、xAI、DeepSeek、OpenRouter等）
- API密钥
- 默认模型
- 搜索引擎（可选）

### 3. 启动应用

```bash
python app.py
```

访问 http://localhost:5000 开始使用

## 配置说明

配置文件 `config.yml` 格式：

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "your-api-key"
  default_model: "gpt-4o"
  temperature: 0.7
  models:
    - name: "gpt-4o"
      max_context: 128  # 单位：K tokens

search:
  provider: "tavily"  # 可选: tavily, jina, brave
  api_key: "your-search-api-key"

workspace_root: "./workspaces"
```

### 支持的LLM提供商

| 提供商 | base_url | 推荐模型 |
|--------|----------|----------|
| OpenAI | https://api.openai.com/v1 | gpt-4o, gpt-4o-mini |
| Google (Gemini) | https://generativelanguage.googleapis.com/v1beta/openai | gemini-2.0-flash |
| Kimi (Moonshot) | https://api.moonshot.cn/v1 | kimi-k2 |
| xAI (Grok) | https://api.x.ai/v1 | grok-2 |
| DeepSeek | https://api.deepseek.com/v1 | deepseek-chat |
| OpenRouter | https://openrouter.ai/api/v1 | openai/gpt-4o |

### 搜索引擎配置

#### Tavily (推荐)
1. 访问 https://tavily.com 注册账号
2. 获取 API Key
3. 在 setup.py 中选择 Tavily 并输入 API Key

#### Jina AI
1. 访问 https://jina.ai 获取 API Key
2. 在 setup.py 中选择 Jina

#### Brave Search
1. 访问 https://brave.com/search/api/ 注册
2. 获取 API Key
3. 在 setup.py 中选择 Brave

## 使用指南

### 开始新的学习

1. 点击首页"开始学习"按钮
2. 输入你想学习的主题（如：Python编程、机器学习基础）
3. AI助手会询问几个问题了解你的背景和目标
4. 确认后AI自动生成学习计划
5. 进入正式教学阶段

### 继续学习

1. 点击首页"继续学习"按钮
2. 选择之前创建的学习工作区
3. 从上次离开的地方继续

### 学习过程中

- **提问**: 随时输入问题，AI会根据学习计划回答
- **练习题**: AI会自动生成练习题巩固知识
- **搜索**: AI可以联网搜索最新信息
- **查看计划**: 点击左侧"查看学习计划"随时查看大纲

### 工作区文件结构

```
workspaces/
├── 20240214_143022_python_basics/    # 工作区目录
│   ├── study_plan.md                  # 学习计划
│   ├── agents.md                      # 学习进度记录
│   ├── history.json                   # 对话历史
│   ├── notes/                         # 笔记目录
│   └── exercises/                     # 练习题目录
```

## 核心机制

### 上下文管理

应用采用分层上下文管理策略：

1. **启动询问阶段**: 隔离上下文，收集学习需求
2. **正式教学阶段**: 固定前缀提示词，最大化KV Cache效率
3. **自动压缩**: 当token数超过阈值80%时，自动压缩历史上下文

### 工具系统

AI助手可随时调用以下工具：

- **generate_exercise**: 生成练习题（选择题、填空题、简答题等）
- **web_search**: 网络搜索获取最新信息
- **file_system**: 读写工作区文件

### 客观题自动验证

选择题、填空题等客观题由前端直接验证，无需LLM介入，节省API调用成本。

## 项目结构

```
ai-learning-assistant/
├── app.py              # Flask主应用
├── setup.py            # 交互式配置向导
├── config.yml          # 配置文件
├── requirements.txt    # Python依赖
├── README.md           # 使用说明
├── static/             # 静态文件
│   ├── css/
│   │   └── style.css   # 全局样式
│   └── js/
│       └── main.js     # 主JavaScript
├── templates/          # HTML模板
│   ├── base.html       # 基础模板
│   ├── index.html      # 首页
│   └── chat.html       # 聊天页面
└── workspaces/         # 工作区目录
```

## 开发

### 调试模式

```bash
FLASK_DEBUG=1 python app.py
```

### 日志

应用日志保存在 `debug.log` 文件中。

## 常见问题

### Q: 如何更换LLM模型？
A: 运行 `python setup.py`，选择"修改LLM配置"即可。

### Q: 搜索功能无法使用？
A: 确保已在配置中设置搜索API Key。如不需要搜索，可在配置中跳过。

### Q: 上下文压缩是什么意思？
A: 当对话token数接近模型限制时，系统会自动总结早期对话内容，保留关键信息，确保教学连贯性。

### Q: 如何导出学习记录？
A: 在聊天页面点击顶部"导出对话"按钮。

## 技术栈

- **后端**: Python 3.8+, Flask
- **前端**: HTML5, CSS3, JavaScript (ES6+)
- **LLM协议**: OpenAI API 格式
- **数据存储**: 本地文件系统 (JSON, Markdown)

## License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 贡献

欢迎提交Issue和Pull Request！

## 更新日志

详细变更记录请查看 [CHANGELOG.md](CHANGELOG.md)。

### v3.0.0 (2026-02-15) - 用户体验优化版
- **自动化流程**：AI收集足够信息后自动生成学习计划，无需手动点击
- **智能教学策略**：优化提示词确保AI主动引导，每次教学要么提问要么出题
- **界面现代化**：移除头像，采用卡片式消息设计，视觉更简洁清晰
- **完整导出功能**：支持标准JSON格式对话记录导出，包含元数据和文件结构
- **教学流程优化**：AI生成第一句话开始教学，移除预设欢迎信息
- **工具调用标准化**：确保出题工具符合OpenAI标准tool参数格式
- **响应式改进**：优化移动端消息卡片显示

### v2.0.0 (2026-02-15)
- **新增**：AI主动结束询问功能，添加`end_inquiry`工具
- **优化**：提示词分离到独立配置文件`prompts.yml`，便于维护
- **改进**：学习计划自适应生成，避免小题大做
- **增强**：前端按钮动画效果，更好的用户体验
- **重构**：引入`PromptManager`类统一管理提示词

### v1.1.0 (2026-02-15)
- **修复**：AI在需求询问阶段就开始教学的问题
- **新增**：工作区状态持久化（`workspace_state.json`）
- **改进**：前端"生成学习计划"按钮和阶段指示器
- **优化**：阶段切换逻辑和用户体验

### v1.0.0 (2026-02-14)
- 初始版本发布
- 支持多LLM提供商
- 上下文压缩机制
- 工具调用系统
- 响应式UI设计
