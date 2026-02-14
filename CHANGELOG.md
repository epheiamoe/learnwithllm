# AI Learning Assistant - 更新日志

所有版本变更记录均在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-02-15

### 已修复
- **阶段切换问题**：修复了AI在需求询问阶段就开始教学的问题
  - 强化`PHASE1_INQUIRY_PROMPT`提示词，明确禁止教学和工具使用
  - 添加明确的阶段结束信号："I have enough information now. Please click the 'Generate Study Plan' button..."
  - 前端添加"生成学习计划"按钮，只在询问阶段显示
  - 实现工作区状态持久化（`workspace_state.json`）

- **工作区状态持久化**：修复了加载现有工作区时阶段被硬编码为"teaching"的问题
  - 新增`workspace_state.json`文件保存工作区状态
  - 保存和恢复`current_phase`、`token_count`、`compressed_context`等状态
  - 确保应用重启后能从正确阶段继续

- **前端用户体验**：
  - 移除基于URL参数的阶段初始化（现在从后端获取）
  - 确保`inquiryHistory`在加载历史消息时正确初始化
  - 防止在已有历史消息时重复发送初始消息
  - 改进阶段指示器的更新逻辑

### 新增
- **工作区状态文件**：`workspace_state.json`包含：
  - `current_phase`: 当前阶段（init/inquiry/teaching）
  - `token_count`: 当前token计数
  - `token_threshold`: token阈值
  - `compressed_context`: 压缩的上下文内容

- **前端UI组件**：
  - "生成学习计划"按钮，带有渐变背景和动画效果
  - 改进的阶段指示器视觉反馈

### 变更
- **后端路由**：
  - `WorkspaceManager.save_workspace()`现在保存工作区状态
  - `WorkspaceManager.get_workspace()`从状态文件加载阶段信息
  - `inquiry_chat`路由明确不传递工具参数

- **前端JavaScript**：
  - 重构阶段初始化逻辑
  - 添加`updatePhaseIndicator()`函数统一管理阶段显示
  - 改进`startInquiry()`函数，防止重复发送初始消息

### 技术细节
- **文件变更**：
  - `app.py`: 修改提示词模板、工作区状态管理
  - `templates/chat.html`: 添加生成学习计划按钮，改进阶段逻辑
  - `static/css/style.css`: 添加按钮样式和动画
  - `AGENTS.md`: 更新常见问题修复部分
  - `structure.md`: 更新工作区文件结构说明

- **API变更**：
  - 无破坏性API变更
  - 新增`workspace_state.json`文件格式

## [1.0.0] - 2026-02-14

### 新增
- 初始版本发布
- 支持多LLM提供商（OpenAI、Google、Kimi、xAI、DeepSeek、OpenRouter等）
- 上下文压缩机制
- 工具调用系统（generate_exercise、web_search、file_system）
- 响应式UI设计，支持深色/浅色模式
- 工作区持久化系统

### 技术栈
- 后端：Python 3.8+, Flask
- 前端：HTML5, CSS3, JavaScript (ES6+)
- LLM协议：OpenAI API 格式
- 数据存储：本地文件系统 (JSON, Markdown)

---

## 维护指南

### 版本发布流程
1. 更新`CHANGELOG.md`文件
2. 更新`README.md`中的版本信息
3. 确保所有测试通过
4. 创建git tag：`git tag -a v1.1.0 -m "版本1.1.0：修复阶段切换问题"`
5. 推送tag：`git push origin v1.1.0`

### 版本号规则
- **主版本号（MAJOR）**：不兼容的API修改
- **次版本号（MINOR）**：向下兼容的功能性新增
- **修订号（PATCH）**：向下兼容的问题修正

### 文档更新要求
每次版本发布必须更新：
1. `CHANGELOG.md` - 详细变更记录
2. `AGENTS.md` - 开发者文档
3. `structure.md` - 项目结构文档
4. `README.md` - 用户文档（如有重大变更）

### 向后兼容性
- 保持现有工作区文件的兼容性
- 新增功能不应破坏现有工作流程
- 数据迁移需要提供明确的升级路径