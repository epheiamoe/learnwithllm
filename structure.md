# AI Learning Assistant - 项目结构文档

## 项目概述

AI协作学习助手是一个基于Python Flask + 原生HTML/CSS/JS的个人智能导师应用。采用结构化上下文管理实现长程教学，确保LLM在超长对话中保持教学连贯性。

## 目录结构

```
ai-learning-assistant/
├── app.py                  # Flask主应用，包含路由、LLM调用逻辑、工具执行
├── setup.py                # 交互式配置向导，首次运行配置和后续修改
├── wsgi.py                 # WSGI入口文件
├── config.yml              # 配置文件（LLM、搜索等）
├── requirements.txt        # Python依赖
├── structure.md            # 本文件 - 项目结构文档
├── AGENTS.md               # AI开发指南
├── README.md               # 用户使用说明
├── LICENSE                 # MIT许可证
├── .gitignore              # Git忽略规则
├── static/                 # 静态文件
│   ├── css/
│   │   └── style.css       # 全局样式（响应式、深色/浅色模式）
│   ├── js/
│   │   └── main.js         # 共享JavaScript工具函数
│   └── index.html          # 静态入口页
├── templates/              # HTML模板（Jinja2）
│   ├── base.html           # 基础模板（导航栏、主题切换、通知容器）
│   ├── index.html          # 首页（新建学习、继续学习）
│   └── chat.html           # 对话页面（侧边栏、消息区域、输入区）
└── workspaces/             # 工作区目录（运行时创建）
    └── {timestamp}_{theme}/    # 每次学习创建的独立工作区
        ├── study_plan.md       # AI生成的学习计划
        ├── agents.md           # 学习进度记录
        ├── history.json        # 对话历史
        ├── notes/              # 笔记目录
        └── exercises/          # 练习题目录
```

## 核心模块说明

### 后端 (app.py)

#### 数据模型
- `Message`: 消息数据类（role, content, timestamp, tool_calls）
- `Workspace`: 工作区数据类（id, theme, path, phase, messages等）

#### 核心类
- `ConfigManager`: 配置管理，加载config.yml
- `WorkspaceManager`: 工作区管理（创建、加载、保存、文件树）
- `ToolExecutor`: 工具执行器（generate_exercise, web_search, file_system）
- `LLMService`: LLM服务（chat_completion, compress_context）

#### 路由
- `GET /`: 首页
- `GET /chat/<workspace_id>`: 聊天页面
- `GET/POST /api/workspaces`: 工作区列表/创建
- `POST /api/workspaces/<id>/inquiry`: 阶段一：需求询问（无工具）
- `POST /api/workspaces/<id>/plan`: 生成学习计划
- `POST /api/workspaces/<id>/chat`: 阶段二：正式教学（有工具）
- `GET /api/workspaces/<id>/messages`: 获取消息历史
- `GET /api/workspaces/<id>/files`: 获取文件树
- `GET /api/workspaces/<id>/files/<path>`: 读取文件
- `POST /api/tools/execute`: 执行工具
- `GET/POST /api/exercises/...`: 练习题相关

#### 提示词模板
- `PHASE1_INQUIRY_PROMPT`: 需求询问阶段系统提示词（无工具）
- `PHASE2_TEACHING_PROMPT`: 正式教学阶段系统提示词（有工具）

### 前端

#### 样式 (style.css)
- CSS变量定义（颜色、阴影、间距等）
- 深色/浅色模式切换（data-theme属性）
- 响应式设计（桌面端、平板、移动端）
- 组件样式（按钮、模态框、消息气泡、代码块等）

#### 页面
- **base.html**: 基础模板，包含导航栏、主题切换、通知容器
- **index.html**: 首页，包含英雄区域、特性介绍、工作区列表、新建学习模态框
- **chat.html**: 对话页面，包含侧边栏（上下文指示器、阶段指示器、文件树）、消息区域、输入区

#### JavaScript
- **main.js**: 共享工具函数（ThemeManager, NotificationManager, MarkdownRenderer等）
- **chat.html内联JS**: 页面特定逻辑（消息发送、流式处理、练习题、文件预览等）

## 数据流

### 新建学习流程
1. 用户输入主题 → POST /api/workspaces
2. 创建工作区目录和agents.md
3. 跳转到chat页面，phase=inquiry
4. AI发送初始询问消息

### 需求询问流程
1. 用户发送消息 → POST /api/workspaces/<id>/inquiry
2. 后端构建PHASE1_INQUIRY_PROMPT（无工具）
3. 流式返回AI响应
4. 前端累积显示消息
5. 用户点击"生成学习计划" → POST /api/workspaces/<id>/plan
6. 生成study_plan.md，更新phase为teaching

### 正式教学流程
1. 用户发送消息 → POST /api/workspaces/<id>/chat
2. 后端构建PHASE2_TEACHING_PROMPT（有工具）
3. 读取study_plan.md和agents.md
4. 流式返回AI响应，可能包含工具调用
5. 前端显示消息，处理工具状态
6. 保存消息到history.json

## 关键设计

### 上下文管理
- **阶段隔离**: 询问阶段和教学阶段使用不同的系统提示词
- **KV Cache优化**: 固定前缀结构（[SYSTEM]到[USER_INPUT]）
- **自动压缩**: Token数超过80%阈值时触发上下文压缩

### 工具系统
- 工具仅在正式教学阶段可用
- 工具调用通过<tool_call>标签实现
- 支持generate_exercise、web_search、file_system

### 工作区持久化
- 所有数据保存在workspaces/目录下
- 每个工作区独立目录，包含study_plan.md、agents.md、history.json
- 可随时关闭浏览器，从agents.md状态恢复

## 配置说明

### config.yml
```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "sk-..."
  default_model: "gpt-4o"
  temperature: 0.7
  models:
    - name: "gpt-4o"
      max_context: 128  # K tokens

search:
  provider: "tavily"  # tavily, jina, brave
  api_key: "..."

workspace_root: "./workspaces"
```

## 开发注意事项

### 添加新工具
1. 在`ToolExecutor`类中添加工具方法
2. 在`PHASE2_TEACHING_PROMPT`中添加工具说明
3. 在`teaching_chat`路由的tools列表中添加工具定义
4. 前端可选：添加工具状态显示

### 修改提示词
- 询问阶段：修改`PHASE1_INQUIRY_PROMPT`
- 教学阶段：修改`PHASE2_TEACHING_PROMPT`

### 前端修改
- 样式：修改`static/css/style.css`
- 共享JS：修改`static/js/main.js`
- 页面逻辑：修改对应templates中的内联JS

## 调试

### 日志
- 应用日志：`debug.log`
- Flask日志：控制台输出

### 常用调试命令
```bash
# 查看工作区内容
ls -la workspaces/

# 查看某个工作区的对话历史
cat workspaces/20240214_143022_xxx/history.json | python -m json.tool

# 查看学习计划
cat workspaces/20240214_143022_xxx/study_plan.md
```
