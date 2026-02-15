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
- 工具通过`<tool_call>`标签调用
- 工具定义只在正式教学阶段传入LLM
- 工具执行结果不保存到对话历史

## 修改指南

### 添加新工具
1. 在`ToolExecutor`类中添加方法（参考现有工具）
2. 在`PHASE2_TEACHING_PROMPT`的[AVAILABLE_TOOLS]部分添加说明
3. 在`teaching_chat`路由的tools列表中添加JSON Schema定义
4. 前端`chat.html`中添加工具状态显示（可选）

### 修改提示词
- 询问阶段：修改`PHASE1_INQUIRY_PROMPT`（app.py第628行左右）
- 教学阶段：修改`PHASE2_TEACHING_PROMPT`（app.py第645行左右）

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

## 常见问题修复

### 问题：AI在需求询问阶段不会主动进入教学
**修复版本**: v2.0.0
**问题描述**: AI在需求询问阶段不会主动结束询问，需要用户手动点击按钮
**解决方案**:
1. 添加`end_inquiry`工具，让AI可以主动结束询问阶段
2. 优化提示词，明确告诉AI在收集足够信息后调用`end_inquiry`工具
3. 前端自动检测`end_inquiry`工具调用，高亮显示生成计划按钮
4. 将提示词分离到独立的`prompts.yml`配置文件

**检查点**:
1. 确认`prompts.yml`文件存在并包含正确的提示词
2. 确认`ToolExecutor`类包含`_end_inquiry`方法
3. 确认`inquiry_chat`路由传递`end_inquiry`工具定义
4. 确认前端`sendInquiryMessage`函数能处理工具调用
5. 确认生成学习计划按钮有脉冲动画效果

### 问题：学习计划过于复杂，小题大做
**修复版本**: v2.0.0
**问题描述**: 简单的学习任务生成了过于复杂的学习计划
**解决方案**:
1. 在`prompts.yml`中添加自适应学习计划生成逻辑
2. 根据主题复杂度和用户背景调整计划详细程度
3. 提供简单、中等、复杂三种计划模板
4. 优化提示词，强调简洁实用

**检查点**:
1. 确认`prompts.yml`中的`phase2_plan_generation`包含自适应逻辑
2. 确认`generate_study_plan`函数使用新的提示词管理器
3. 确认学习计划输出简洁明了，适合用户水平

### 问题：无法正常进入正式教学
**检查点**:
1. `generateStudyPlan`是否成功执行
2. `study_plan.md`是否成功写入
3. 工作区`current_phase`是否更新为"teaching"
4. `workspace_state.json`是否包含正确的阶段信息

### 问题：工具调用不生效
**检查点**:
1. 是否在正式教学阶段（phase === 'teaching'）
2. tools列表是否正确传递给LLM
3. 工具JSON Schema是否正确定义
4. 后端是否遵循OpenAI工具调用规范（AI请求 -> 执行工具 -> 返回结果）
5. 前端是否正确处理`data.exercise`事件

### 问题：AI重复询问已收集的信息
**检查点**:
1. 确认`prompts.yml`中phase3_teaching提示词包含"学习计划来源"说明
2. 确认AI清楚学习计划是自己生成的
3. 检查教学阶段是否加载了正确的study_plan.md

### 问题：练习题不显示在右侧栏
**检查点**:
1. 确认`showExercise`函数调用了`addExerciseToSidebar`
2. 检查`exercises`数组是否正确更新
3. 确认`updateExerciseList`函数正确渲染列表
4. 检查CSS中`.exercise-sidebar`样式是否正确加载

### 问题：右侧题目栏无法展开/收起
**检查点**:
1. CSS中`.exercise-sidebar.collapsed`样式是否正确
2. `initExerciseSidebar`函数是否正确初始化事件监听
3. 移动端`.exercise-sidebar.mobile-open`样式是否正确
4. 检查是否有JavaScript错误阻止事件绑定

### 问题：练习题内容为空
**修复版本**: v3.2.0
**问题描述**: AI调用`generate_exercise`工具但返回空题目内容
**解决方案**:
1. 检查`prompts.yml`中phase3_teaching提示词是否包含工具调用示例
2. 确认AI理解必须提供完整的题目参数（question、type、options等）
3. 验证`_generate_exercise`函数参数验证逻辑是否生效
4. 检查工具调用错误信息是否正确返回给AI

**检查点**:
1. 确认`prompts.yml`中的工具提示词包含详细要求和示例
2. 检查`_generate_exercise`函数是否验证必要参数
3. 查看debug.log中工具调用是否有错误信息
4. 确认AI收到错误提示后能重新正确调用工具

### 问题：工具调用参数不完整
**修复版本**: v3.3.0
**问题描述**: AI调用工具（如`file_system`）但参数为空或不完整
**解决方案**:
1. 优化`prompts.yml`中工具提示词，添加具体的调用示例
2. 增强工具函数参数验证，提供详细的错误提示和修复建议
3. 确保工具执行失败时返回结构化错误信息（包含`error`和`hint`字段）
4. 前端添加工具调用可视化反馈，在聊天区域显示工具状态

**检查点**:
1. 确认`prompts.yml`中的工具说明包含完整的参数要求和示例
2. 检查工具函数（如`_file_system`）是否验证所有必要参数
3. 测试工具调用失败时是否返回有意义的错误信息
4. 验证前端是否正确显示工具调用状态和错误提示

### 问题：教学阶段流程阻塞
**修复版本**: v3.3.0
**问题描述**: AI调用`end_inquiry`工具后仍需手动点击"生成学习计划"按钮
**解决方案**:
1. 修复前端`inquiryComplete`状态管理，确保自动触发学习计划生成
2. 改进`inquiryHistory`更新逻辑，确保包含完整的对话历史
3. 添加调试日志帮助诊断流程问题
4. 确保后端正确发送`inquiry_complete`信号

**检查点**:
1. 检查`sendInquiryMessage`函数是否正确处理`inquiry_complete`信号
2. 验证`inquiryHistory`是否包含所有用户和AI消息
3. 查看浏览器控制台调试日志，确认流程是否正确执行
4. 测试AI调用`end_inquiry`后是否自动进入教学阶段

### 问题：AI输出频繁滚动
**修复版本**: v3.2.0
**问题描述**: AI流式输出时频繁自动滚动，干扰用户阅读
**解决方案**:
1. 修改流式响应处理，只在消息开始时滚动一次
2. 区分用户消息和AI消息的滚动逻辑
3. 保持用户阅读位置的稳定性

**检查点**:
1. 确认`appendMessage`函数只在用户消息时滚动
2. 检查流式响应处理中的滚动逻辑是否正确
3. 测试AI长回复时是否保持阅读位置
4. 验证用户发送消息后是否正常滚动到底部

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
