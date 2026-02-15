#!/usr/bin/env python3
"""
AI Learning Assistant - Main Application
AI协作学习助手主服务端

MIT License
"""

import os
import sys
import json
import yaml
import time
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator, Tuple
from dataclasses import dataclass, field, asdict
from functools import wraps
import threading

from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import requests

# ==================== 配置和日志 ====================

CONFIG_FILE = "config.yml"
DEBUG_LOG = "debug.log"

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(DEBUG_LOG, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)
app.config['JSON_AS_ASCII'] = False

# ==================== 数据模型 ====================

@dataclass
class Message:
    role: str
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

@dataclass
class Workspace:
    id: str
    theme: str
    created_at: str
    path: str
    current_phase: str = "init"  # init, inquiry, teaching
    token_count: int = 0
    token_threshold: int = 0
    messages: List[Dict] = field(default_factory=list)
    compressed_context: str = ""

# ==================== 配置管理 ====================

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if not os.path.exists(CONFIG_FILE):
            logger.error(f"配置文件不存在: {CONFIG_FILE}")
            logger.info("请先运行: python setup.py")
            sys.exit(1)
        
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info("配置文件加载成功")
            return config
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            sys.exit(1)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.config.get('llm', {})
    
    def get_search_config(self) -> Dict[str, Any]:
        """获取搜索配置"""
        return self.config.get('search', {})
    
    def get_workspace_root(self) -> str:
        """获取工作区根目录"""
        root = self.config.get('workspace_root', './workspaces')
        return os.path.abspath(root)
    
    def get_model_max_context(self, model_name: str) -> int:
        """获取模型最大上下文"""
        models = self.config.get('llm', {}).get('models', [])
        for model in models:
            if model.get('name') == model_name:
                return model.get('max_context', 128) * 1000
        return 128000  # 默认128K

config_manager = ConfigManager()

# ==================== 工作区管理 ====================

class WorkspaceManager:
    """工作区管理器"""
    
    def __init__(self):
        self.root = config_manager.get_workspace_root()
        self._ensure_root()
        self.active_workspaces: Dict[str, Workspace] = {}
    
    def _ensure_root(self):
        """确保工作区根目录存在"""
        os.makedirs(self.root, exist_ok=True)
        logger.debug(f"工作区根目录: {self.root}")
    
    def _sanitize_filename(self, name: str) -> str:
        """清理文件名"""
        # 移除非法字符
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # 限制长度
        name = name[:50].strip()
        return name
    
    def create_workspace(self, theme: str) -> Workspace:
        """创建新工作区"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        theme_slug = self._sanitize_filename(theme)
        workspace_id = f"{timestamp}_{theme_slug}"
        
        path = os.path.join(self.root, workspace_id)
        os.makedirs(path, exist_ok=True)
        
        # 创建子目录
        os.makedirs(os.path.join(path, 'notes'), exist_ok=True)
        os.makedirs(os.path.join(path, 'exercises'), exist_ok=True)
        
        workspace = Workspace(
            id=workspace_id,
            theme=theme,
            created_at=datetime.now().isoformat(),
            path=path,
            token_threshold=int(config_manager.get_model_max_context(
                config_manager.get_llm_config().get('default_model', 'gpt-4o')
            ) * 0.8)
        )
        
        self.active_workspaces[workspace_id] = workspace
        logger.info(f"创建工作区: {workspace_id}")
        return workspace
    
    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """获取工作区"""
        if workspace_id in self.active_workspaces:
            return self.active_workspaces[workspace_id]
        
        # 尝试从磁盘加载
        path = os.path.join(self.root, workspace_id)
        if os.path.exists(path):
            workspace = self._load_workspace_from_disk(workspace_id, path)
            if workspace:
                self.active_workspaces[workspace_id] = workspace
                return workspace
        return None
    
    def _load_workspace_from_disk(self, workspace_id: str, path: str) -> Optional[Workspace]:
        """从磁盘加载工作区"""
        try:
            # 读取agents.md获取基本信息
            agents_path = os.path.join(path, 'agents.md')
            theme = workspace_id  # 默认使用ID作为主题
            
            if os.path.exists(agents_path):
                with open(agents_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 尝试提取主题
                    match = re.search(r'Theme:\s*(.+)', content)
                    if match:
                        theme = match.group(1).strip()
            
            # 读取历史消息
            history_path = os.path.join(path, 'history.json')
            messages = []
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    messages = json.load(f)

            # 读取工作区状态
            state_path = os.path.join(path, 'workspace_state.json')
            current_phase = "inquiry"  # 默认值
            token_count = 0
            token_threshold = int(config_manager.get_model_max_context(
                config_manager.get_llm_config().get('default_model', 'gpt-4o')
            ) * 0.8)
            compressed_context = ""

            if os.path.exists(state_path):
                try:
                    with open(state_path, 'r', encoding='utf-8') as f:
                        state = json.load(f)
                        current_phase = state.get('current_phase', 'inquiry')
                        token_count = state.get('token_count', 0)
                        token_threshold = state.get('token_threshold', token_threshold)
                        compressed_context = state.get('compressed_context', '')
                except Exception as e:
                    logger.error(f"加载工作区状态失败: {str(e)}")

            workspace = Workspace(
                id=workspace_id,
                theme=theme,
                created_at=datetime.fromtimestamp(os.path.getctime(path)).isoformat(),
                path=path,
                current_phase=current_phase,
                messages=messages,
                token_count=token_count,
                token_threshold=token_threshold,
                compressed_context=compressed_context
            )
            
            logger.info(f"从磁盘加载工作区: {workspace_id}")
            return workspace
        except Exception as e:
            logger.error(f"加载工作区失败: {str(e)}")
            return None
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作区"""
        workspaces = []
        try:
            for item in os.listdir(self.root):
                item_path = os.path.join(self.root, item)
                if os.path.isdir(item_path):
                    # 读取agents.md获取主题
                    theme = item
                    agents_path = os.path.join(item_path, 'agents.md')
                    if os.path.exists(agents_path):
                        with open(agents_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            match = re.search(r'Theme:\s*(.+)', content)
                            if match:
                                theme = match.group(1).strip()
                    
                    workspaces.append({
                        'id': item,
                        'theme': theme,
                        'created_at': datetime.fromtimestamp(os.path.getctime(item_path)).isoformat(),
                        'path': item_path
                    })
        except Exception as e:
            logger.error(f"列出工作区失败: {str(e)}")
        
        # 按创建时间排序（最新的在前）
        workspaces.sort(key=lambda x: x['created_at'], reverse=True)
        return workspaces
    
    def save_workspace(self, workspace: Workspace):
        """保存工作区状态"""
        try:
            # 保存历史消息
            history_path = os.path.join(workspace.path, 'history.json')
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(workspace.messages, f, ensure_ascii=False, indent=2)

            # 保存工作区状态（包括阶段信息）
            state_path = os.path.join(workspace.path, 'workspace_state.json')
            state = {
                'current_phase': workspace.current_phase,
                'token_count': workspace.token_count,
                'token_threshold': workspace.token_threshold,
                'compressed_context': workspace.compressed_context
            }
            with open(state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

            logger.debug(f"工作区已保存: {workspace.id}")
        except Exception as e:
            logger.error(f"保存工作区失败: {str(e)}")
    
    def get_file_tree(self, workspace_id: str) -> List[Dict[str, Any]]:
        """获取工作区文件树"""
        workspace = self.get_workspace(workspace_id)
        if not workspace:
            return []
        
        file_tree = []
        try:
            for root, dirs, files in os.walk(workspace.path):
                rel_path = os.path.relpath(root, workspace.path)
                level = rel_path.count(os.sep) if rel_path != '.' else 0
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_file_path = os.path.relpath(file_path, workspace.path)
                    file_tree.append({
                        'name': file,
                        'path': rel_file_path,
                        'level': level,
                        'size': os.path.getsize(file_path)
                    })
        except Exception as e:
            logger.error(f"获取文件树失败: {str(e)}")
        
        return file_tree

workspace_manager = WorkspaceManager()

# ==================== 工具系统 ====================

class ToolExecutor:
    """工具执行器"""

    def __init__(self):
        self.tools = {
            'generate_exercise': self._generate_exercise,
            'web_search': self._web_search,
            'file_system': self._file_system,
            'end_inquiry': self._end_inquiry  # 新增：结束询问工具
        }
    
    def execute(self, tool_name: str, params: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """执行工具"""
        if tool_name not in self.tools:
            return {'error': f'未知工具: {tool_name}'}
        
        try:
            logger.info(f"执行工具: {tool_name}")
            return self.tools[tool_name](params, workspace)
        except Exception as e:
            logger.error(f"工具执行失败 {tool_name}: {str(e)}")
            return {'error': str(e)}
    
    def _generate_exercise(self, params: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """生成练习题"""
        # 检查必要参数
        if not params.get('question'):
            return {'error': '题目内容不能为空', 'hint': '请提供完整的题目内容，包括question、type等参数'}

        exercise_type = params.get('type', 'choice')

        # 根据题目类型验证必要参数
        if exercise_type == 'choice':
            options = params.get('options', [])
            if len(options) < 2:
                return {'error': '选择题必须提供至少2个选项', 'hint': '请提供完整的选项数组'}
            if not params.get('correct_answers'):
                return {'error': '选择题必须提供正确答案', 'hint': '请提供correct_answers参数'}

        elif exercise_type == 'fill_blank':
            blanks = params.get('blanks', [])
            if not blanks:
                return {'error': '填空题必须提供空白位置', 'hint': '请提供blanks参数'}
            if not params.get('correct_answers'):
                return {'error': '填空题必须提供正确答案', 'hint': '请提供correct_answers参数'}

        exercise = {
            'type': exercise_type,
            'question': params.get('question', ''),
            'options': params.get('options', []),
            'blanks': params.get('blanks', []),
            'correct_answers': params.get('correct_answers', []),
            'explanation': params.get('explanation', ''),
            'difficulty': params.get('difficulty', 'medium'),
            'created_at': datetime.now().isoformat()
        }

        # 保存到工作区
        exercise_id = f"ex_{int(time.time())}"
        exercise_path = os.path.join(workspace.path, 'exercises', f"{exercise_id}.json")

        try:
            with open(exercise_path, 'w', encoding='utf-8') as f:
                json.dump(exercise, f, ensure_ascii=False, indent=2)
            logger.info(f"练习题已保存: {exercise_id}")
            return {'success': True, 'exercise_id': exercise_id, 'exercise': exercise}
        except Exception as e:
            return {'error': str(e)}
    
    def _web_search(self, params: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """网络搜索"""
        search_config = config_manager.get_search_config()
        provider = search_config.get('provider', '')
        api_key = search_config.get('api_key', '')
        
        if not provider or not api_key:
            return {'error': '搜索功能未配置', 'results': []}
        
        query = params.get('query', '')
        max_results = params.get('max_results', 5)
        
        try:
            if provider == 'tavily':
                return self._search_tavily(query, api_key, max_results)
            elif provider == 'jina':
                return self._search_jina(query, api_key, max_results)
            elif provider == 'brave':
                return self._search_brave(query, api_key, max_results)
            else:
                return {'error': f'不支持的搜索提供商: {provider}', 'results': []}
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            return {'error': str(e), 'results': []}
    
    def _search_tavily(self, query: str, api_key: str, max_results: int) -> Dict[str, Any]:
        """Tavily搜索"""
        response = requests.post(
            'https://api.tavily.com/search',
            headers={'Content-Type': 'application/json'},
            json={
                'api_key': api_key,
                'query': query,
                'max_results': max_results,
                'search_depth': 'basic'
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for result in data.get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('content', '')
                })
            return {'success': True, 'results': results}
        else:
            return {'error': f'Tavily API错误: {response.status_code}', 'results': []}
    
    def _search_jina(self, query: str, api_key: str, max_results: int) -> Dict[str, Any]:
        """Jina AI搜索"""
        headers = {'Authorization': f'Bearer {api_key}'}
        response = requests.get(
            f'https://s.jina.ai/http://{requests.utils.quote(query)}',
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            # Jina返回的是文本格式
            content = response.text
            return {
                'success': True,
                'results': [{'title': '搜索结果', 'url': '', 'content': content[:2000]}]
            }
        else:
            return {'error': f'Jina API错误: {response.status_code}', 'results': []}
    
    def _search_brave(self, query: str, api_key: str, max_results: int) -> Dict[str, Any]:
        """Brave搜索"""
        headers = {'X-Subscription-Token': api_key}
        response = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            headers=headers,
            params={'q': query, 'count': max_results},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = []
            for result in data.get('web', {}).get('results', []):
                results.append({
                    'title': result.get('title', ''),
                    'url': result.get('url', ''),
                    'content': result.get('description', '')
                })
            return {'success': True, 'results': results}
        else:
            return {'error': f'Brave API错误: {response.status_code}', 'results': []}
    
    def _file_system(self, params: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """文件系统操作"""
        action = params.get('action', '')
        path = params.get('path', '')
        content = params.get('content', '')
        edit_instruction = params.get('edit_instruction', '')

        # 验证必要参数
        if not action:
            return {'error': '缺少必要参数: action', 'hint': '请提供action参数，必须是read/write/edit/delete/mkdir之一'}
        if not path:
            return {'error': '缺少必要参数: path', 'hint': '请提供path参数，指定文件或目录路径'}

        # 验证action值
        valid_actions = ['read', 'write', 'edit', 'delete', 'mkdir']
        if action not in valid_actions:
            return {'error': f'无效的action: {action}', 'hint': f'action必须是以下之一: {", ".join(valid_actions)}'}

        # 验证特定操作的必要参数
        if action == 'write' and not content:
            return {'error': 'write操作需要content参数', 'hint': '请提供content参数，包含要写入的内容'}
        if action == 'edit' and not edit_instruction:
            return {'error': 'edit操作需要edit_instruction参数', 'hint': '请提供edit_instruction参数，格式：原文本->新文本'}

        # 确保路径安全（限制在工作区内）
        full_path = os.path.normpath(os.path.join(workspace.path, path))
        if not full_path.startswith(workspace.path):
            return {'error': '非法路径', 'hint': '路径必须在工作区内'}

        try:
            if action == 'read':
                if not os.path.exists(full_path):
                    return {'error': f'文件不存在: {path}', 'hint': '请检查路径是否正确'}
                with open(full_path, 'r', encoding='utf-8') as f:
                    return {'success': True, 'content': f.read()}

            elif action == 'write':
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {'success': True, 'message': f'文件已写入: {path}'}

            elif action == 'edit':
                if not os.path.exists(full_path):
                    return {'error': f'文件不存在: {path}', 'hint': '请检查路径是否正确'}
                with open(full_path, 'r', encoding='utf-8') as f:
                    original = f.read()
                # 简单的替换逻辑（实际应用中可以更复杂）
                try:
                    old_text = edit_instruction.split('->')[0].strip()
                    new_text = edit_instruction.split('->')[1].strip()
                    modified = original.replace(old_text, new_text)
                except IndexError:
                    return {'error': 'edit_instruction格式错误', 'hint': '格式应为：原文本->新文本'}
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(modified)
                return {'success': True, 'message': f'文件已编辑: {path}'}

            elif action == 'delete':
                if os.path.exists(full_path):
                    os.remove(full_path)
                    return {'success': True, 'message': f'文件已删除: {path}'}
                return {'error': f'文件不存在: {path}', 'hint': '请检查路径是否正确'}

            elif action == 'mkdir':
                os.makedirs(full_path, exist_ok=True)
                return {'success': True, 'message': f'目录已创建: {path}'}

            else:
                return {'error': f'未知操作: {action}', 'hint': f'action必须是以下之一: {", ".join(valid_actions)}'}

        except Exception as e:
            return {'error': str(e), 'hint': '请检查参数格式是否正确'}

    def _end_inquiry(self, params: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """结束询问阶段（特殊工具，仅AI可调用）"""
        # 这个工具由AI在询问阶段结束时调用
        # 它不会真正执行什么操作，只是作为一个信号

        summary = params.get('summary', '')
        logger.info(f"AI请求结束询问阶段，总结: {summary[:100]}...")

        return {
            'success': True,
            'message': '询问阶段已结束，可以生成学习计划',
            'summary': summary,
            'inquiry_complete': True
        }

tool_executor = ToolExecutor()

# ==================== LLM服务 ====================

class LLMService:
    """LLM服务"""
    
    def __init__(self):
        self.config = config_manager.get_llm_config()
        self.base_url = self.config.get('base_url', '').rstrip('/')
        self.api_key = self.config.get('api_key', '')
        self.model = self.config.get('default_model', 'gpt-4o')
        self.temperature = self.config.get('temperature', 0.7)
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], 
                       stream: bool = True,
                       tools: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """聊天补全（流式）"""
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': self.temperature,
            'stream': stream
        }
        
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=payload,
                stream=stream,
                timeout=120
            )
            
            if response.status_code != 200:
                error_msg = f"LLM API错误: {response.status_code}"
                try:
                    error_data = response.json()
                    error_msg += f" - {error_data.get('error', {}).get('message', '')}"
                except:
                    error_msg += f" - {response.text[:200]}"
                logger.error(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return
            
            if stream:
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                yield f"data: [DONE]\n\n"
                                break
                            try:
                                chunk = json.loads(data)
                                yield f"data: {json.dumps(chunk)}\n\n"
                            except json.JSONDecodeError:
                                continue
            else:
                data = response.json()
                yield f"data: {json.dumps(data)}\n\n"
                yield f"data: [DONE]\n\n"
        
        except Exception as e:
            logger.error(f"LLM请求失败: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    def compress_context(self, messages: List[Dict[str, str]], 
                        study_plan: str,
                        agent_state: str) -> str:
        """压缩上下文"""
        compression_prompt = f"""[SYSTEM] Context compression required.
Create a concise summary of the learning session preserving:
- Key concepts taught so far
- Student's weak points and common mistakes
- Current topic progress (% of study_plan completed)
- Any pending exercises or unresolved questions

Format: Structured markdown with clear headings.

[STUDY_PLAN]
{study_plan}

[AGENT_STATE]
{agent_state}

[CONVERSATION_HISTORY]
"""
        
        # 添加最近的消息
        for msg in messages[-10:]:
            compression_prompt += f"\n{msg['role']}: {msg['content'][:500]}"
        
        compression_messages = [
            {'role': 'system', 'content': 'You are a context compression assistant.'},
            {'role': 'user', 'content': compression_prompt}
        ]
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json={
                    'model': self.model,
                    'messages': compression_messages,
                    'temperature': 0.3,
                    'max_tokens': 2000,
                    'stream': False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data['choices'][0]['message']['content']
                return summary
            else:
                logger.error(f"上下文压缩失败: {response.status_code}")
                return "[Context compression failed - using recent messages only]"
        
        except Exception as e:
            logger.error(f"上下文压缩异常: {str(e)}")
            return "[Context compression error]"

llm_service = LLMService()

# ==================== 提示词管理 ====================

class PromptManager:
    """提示词管理器"""

    def __init__(self):
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, Any]:
        """加载提示词配置"""
        prompts_file = "prompts.yml"
        if not os.path.exists(prompts_file):
            logger.warning(f"提示词配置文件不存在: {prompts_file}，使用默认提示词")
            return self._get_default_prompts()

        try:
            with open(prompts_file, 'r', encoding='utf-8') as f:
                prompts = yaml.safe_load(f)
            logger.info("提示词配置加载成功")
            return prompts
        except Exception as e:
            logger.error(f"加载提示词配置失败: {str(e)}，使用默认提示词")
            return self._get_default_prompts()

    def _get_default_prompts(self) -> Dict[str, Any]:
        """获取默认提示词"""
        return {
            'phase1_inquiry': {
                'system': """# 角色：学习需求分析师

## 核心任务
通过3-5个精准问题，快速了解用户的学习需求。

## 严格规则
1. **禁止教学**：此阶段只提问，不提供任何教学、解释或答案
2. **禁止工具**：不使用任何工具
3. **禁止建议**：不提供学习建议或资源推荐
4. **专注提问**：每次只问一个问题，等待用户回答后再问下一个

## 提问框架
按以下顺序收集关键信息：
1. **学习目标**：想达到什么具体成果？
2. **当前水平**：对主题有多少了解？
3. **时间投入**：每周能投入多少时间学习？
4. **学习偏好**：更喜欢理论讲解、实践练习还是项目驱动？

## 结束条件
当收集到足够信息（通常3-5个问题）时，使用以下标准结束语：
"我已经了解了你的学习需求。请点击「生成学习计划」按钮，我将为你制定个性化的学习方案。"

## 响应风格
- 简洁直接，避免冗长
- 问题具体明确，易于回答
- 保持友好但专业的语气"""
            },
            'phase2_plan_generation': {
                'system': """# 角色：课程设计师

## 任务
根据需求询问阶段的对话，制定一个**简洁实用**的学习计划。

## 自适应原则
1. **根据用户背景调整**：新手用简单结构，有基础用中等结构
2. **根据主题复杂度调整**：简单概念用简单计划，系统知识用详细计划
3. **根据时间投入调整**：时间少则聚焦核心，时间多则全面覆盖

## 输出要求
- 使用Markdown格式
- 语言简洁明了
- 避免过度学术化
- 提供可执行的建议"""
            },
            'phase3_teaching': {
                'system': """[SYSTEM]
角色：个性化学习导师

当前上下文限制：{max_context}K tokens
Token使用情况：{token_count} / {token_threshold}

## 教学原则
1. **循序渐进**：按照学习计划逐步推进
2. **因材施教**：根据学生水平调整教学深度
3. **注重实践**：理论结合实践，及时练习

## 工具使用规范
需要调用工具时，使用标准格式：
<tool_call>{"name": "工具名称", "parameters": {参数}}</tool_call>

## 上下文管理
[STUDY_PLAN]
{study_plan}

[AGENT_STATE]
{agent_state}

{lesson_context}

[最近对话]
{recent_exchanges}

[工作区文件]
{file_tree}

## 响应风格
- 使用Markdown格式化内容
- 代码示例放在代码块中
- 重要概念加粗强调
- 保持友好鼓励的语气"""
            },
            'end_phrases': {
                'inquiry_complete': "我已经了解了你的学习需求。请点击「生成学习计划」按钮，我将为你制定个性化的学习方案。",
                'teaching_welcome': "[教学开始] 已根据你的需求制定学习计划，现在开始正式学习。\n\n你可以随时问我问题，我会根据计划引导你学习。点击左侧\"查看学习计划\"可以随时查看完整的学习大纲。"
            }
        }

    def get_inquiry_prompt(self, user_input: str = "") -> str:
        """获取询问阶段提示词"""
        prompt = self.prompts.get('phase1_inquiry', {}).get('system', '')
        if user_input:
            prompt += f"\n\n当前用户输入: {user_input}"
        return prompt

    def get_plan_generation_prompt(self, inquiry_summary: str) -> str:
        """获取学习计划生成提示词"""
        base_prompt = self.prompts.get('phase2_plan_generation', {}).get('system', '')
        return f"{base_prompt}\n\n需求询问总结:\n{inquiry_summary}"

    def get_teaching_prompt(self, **kwargs) -> str:
        """获取教学阶段提示词"""
        prompt_template = self.prompts.get('phase3_teaching', {}).get('system', '')

        # 替换变量
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            prompt_template = prompt_template.replace(placeholder, str(value))

        return prompt_template

    def get_end_phrase(self, phrase_type: str) -> str:
        """获取结束语"""
        return self.prompts.get('end_phrases', {}).get(phrase_type, '')

prompt_manager = PromptManager()

# ==================== 路由 ====================

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/chat/<workspace_id>')
def chat(workspace_id):
    """聊天页面"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return "工作区不存在", 404
    return render_template('chat.html', workspace_id=workspace_id, theme=workspace.theme)

@app.route('/api/workspaces', methods=['GET'])
def list_workspaces():
    """列出所有工作区"""
    workspaces = workspace_manager.list_workspaces()
    return jsonify({'success': True, 'workspaces': workspaces})

@app.route('/api/workspaces', methods=['POST'])
def create_workspace():
    """创建工作区"""
    data = request.json
    theme = data.get('theme', '').strip()
    
    if not theme:
        return jsonify({'success': False, 'error': '主题不能为空'}), 400
    
    workspace = workspace_manager.create_workspace(theme)
    
    # 初始化agents.md
    agents_content = f"""# Learning Session Agent State

Theme: {theme}
Created: {workspace.created_at}

## Student Profile
- Learning Goal: [To be filled]
- Background: [To be filled]
- Preferred Depth: [To be filled]
- Time Commitment: [To be filled]

## Progress Tracking
- Current Topic: [Not started]
- Topics Completed: []
- Weak Points: []
- Strengths: []

## Session Notes
"""
    
    agents_path = os.path.join(workspace.path, 'agents.md')
    with open(agents_path, 'w', encoding='utf-8') as f:
        f.write(agents_content)
    
    return jsonify({
        'success': True,
        'workspace': {
            'id': workspace.id,
            'theme': workspace.theme,
            'created_at': workspace.created_at
        }
    })

@app.route('/api/workspaces/<workspace_id>/inquiry', methods=['POST'])
def inquiry_chat(workspace_id):
    """阶段一：启动询问（允许AI调用end_inquiry工具）"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404

    data = request.json
    user_input = data.get('message', '')
    history = data.get('history', [])

    # 构建系统提示词
    system_prompt = prompt_manager.get_inquiry_prompt(user_input)

    # 构建消息列表
    messages = [{'role': 'system', 'content': system_prompt}]
    for msg in history:
        messages.append({'role': msg['role'], 'content': msg['content']})
    messages.append({'role': 'user', 'content': user_input})

    # 定义询问阶段可用的工具（仅end_inquiry）
    inquiry_tools = [
        {
            "type": "function",
            "function": {
                "name": "end_inquiry",
                "description": "结束需求询问阶段，表示已收集足够信息可以生成学习计划",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "对收集到的学习需求的简要总结"
                        }
                    },
                    "required": ["summary"]
                }
            }
        }
    ]

    def generate():
        full_response = ""
        tool_calls_buffer = []

        for chunk in llm_service.chat_completion(messages, stream=True, tools=inquiry_tools):
            if not chunk.startswith('data: '):
                continue

            data_str = chunk[6:]
            if data_str == '[DONE]':
                break

            try:
                data = json.loads(data_str)
            except:
                continue

            if 'error' in data:
                yield f"data: {json.dumps({'error': data['error']})}\n\n"
                return

            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                delta = choice.get('delta', {})

                # 处理工具调用
                if 'tool_calls' in delta:
                    for tc in delta['tool_calls']:
                        tool_calls_buffer.append(tc)
                        if 'function' in tc and 'name' in tc['function']:
                            tool_name = tc['function']['name']
                            # 只发送工具开始状态，不发送inquiry_complete状态
                            yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'status': 'started'}})}\n\n"

                # 处理普通内容
                content = delta.get('content', '')
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"

        # 如果有工具调用，执行它们
        if tool_calls_buffer:
            for tc in tool_calls_buffer:
                if 'function' in tc and tc['function']['name'] == 'end_inquiry':
                    # 执行end_inquiry工具
                    params_str = tc['function'].get('arguments', '{}')
                    try:
                        # 处理可能的空参数
                        if not params_str or params_str.strip() == '':
                            params_dict = {}
                        else:
                            params_dict = json.loads(params_str)

                        result = tool_executor.execute('end_inquiry', params_dict, workspace)
                        if result.get('inquiry_complete'):
                            yield f"data: {json.dumps({'inquiry_complete': True, 'summary': result.get('summary', '')})}\n\n"
                    except json.JSONDecodeError as e:
                        logger.error(f"解析end_inquiry参数失败: {str(e)}, params: {params_str}")
                        # 即使解析失败，也标记询问完成
                        yield f"data: {json.dumps({'inquiry_complete': True, 'summary': 'AI已收集足够信息'})}\n\n"
                    except Exception as e:
                        logger.error(f"执行end_inquiry工具失败: {str(e)}")
                        # 即使执行失败，也标记询问完成
                        yield f"data: {json.dumps({'inquiry_complete': True, 'summary': 'AI已收集足够信息'})}\n\n"

        yield f"data: {json.dumps({'done': True, 'full_response': full_response})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/workspaces/<workspace_id>/plan', methods=['POST'])
def generate_study_plan(workspace_id):
    """生成学习计划"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404

    data = request.json
    inquiry_history = data.get('history', [])

    # 构建询问总结
    inquiry_summary = ""
    for msg in inquiry_history:
        inquiry_summary += f"\n{msg['role']}: {msg['content'][:200]}"  # 限制长度

    # 使用提示词管理器构建提示词
    plan_prompt = prompt_manager.get_plan_generation_prompt(inquiry_summary)

    messages = [
        {'role': 'system', 'content': plan_prompt}
    ]
    
    response_chunks = []
    for chunk in llm_service.chat_completion(messages, stream=False):
        if chunk.startswith('data: ') and chunk != 'data: [DONE]\n\n':
            data = json.loads(chunk[6:])
            if 'choices' in data:
                content = data['choices'][0]['message']['content']
                response_chunks.append(content)
    
    study_plan = ''.join(response_chunks)
    
    # 保存study_plan.md
    plan_path = os.path.join(workspace.path, 'study_plan.md')
    with open(plan_path, 'w', encoding='utf-8') as f:
        f.write(study_plan)
    
    # 更新工作区阶段
    workspace.current_phase = 'teaching'
    workspace_manager.save_workspace(workspace)
    
    return jsonify({'success': True, 'study_plan': study_plan})

@app.route('/api/workspaces/<workspace_id>/chat', methods=['POST'])
def teaching_chat(workspace_id):
    """阶段二：正式教学"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    data = request.json
    user_input = data.get('message', '')
    
    # 读取study_plan.md
    study_plan_path = os.path.join(workspace.path, 'study_plan.md')
    study_plan = ""
    if os.path.exists(study_plan_path):
        with open(study_plan_path, 'r', encoding='utf-8') as f:
            study_plan = f.read()
    
    # 读取agents.md
    agents_path = os.path.join(workspace.path, 'agents.md')
    agent_state = ""
    if os.path.exists(agents_path):
        with open(agents_path, 'r', encoding='utf-8') as f:
            agent_state = f.read()
    
    # 检查是否需要上下文压缩
    lesson_context = ""
    if workspace.compressed_context:
        lesson_context = f"[LESSON_CONTEXT - Compressed]\n{workspace.compressed_context}"
    
    # 获取最近消息（保留最近5轮）
    recent_messages = workspace.messages[-10:] if len(workspace.messages) > 10 else workspace.messages
    recent_exchanges = "\n".join([f"{m['role']}: {m['content'][:500]}" for m in recent_messages])
    
    # 获取文件树
    file_tree = workspace_manager.get_file_tree(workspace_id)
    file_tree_str = "\n".join([f["path"] for f in file_tree[:20]])  # 限制数量
    
    # 使用提示词管理器构建系统提示词
    max_context = config_manager.get_model_max_context(llm_service.model) // 1000
    system_prompt = prompt_manager.get_teaching_prompt(
        max_context=max_context,
        token_count=workspace.token_count,
        token_threshold=workspace.token_threshold,
        study_plan=study_plan,
        agent_state=agent_state,
        lesson_context=lesson_context,
        recent_exchanges=recent_exchanges,
        file_tree=file_tree_str
    )
    
    # 构建消息列表
    messages = [{'role': 'system', 'content': system_prompt}]
    messages.extend(workspace.messages)
    messages.append({'role': 'user', 'content': user_input})
    
    # 定义可用工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "generate_exercise",
                "description": "Generate a practice exercise for the student",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["fill_blank", "choice", "short_answer", "match", "multi_fill"]
                        },
                        "question": {"type": "string"},
                        "options": {"type": "array", "items": {"type": "string"}},
                        "blanks": {"type": "array", "items": {"type": "string"}},
                        "correct_answers": {"type": "array", "items": {"type": "string"}},
                        "explanation": {"type": "string"},
                        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]}
                    },
                    "required": ["type", "question"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "default": 5}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "file_system",
                "description": "Read, write, or edit files in the workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["read", "write", "edit", "delete", "mkdir"]},
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "edit_instruction": {"type": "string"}
                    },
                    "required": ["action", "path"]
                }
            }
        }
    ]
    
    def generate():
        full_response = ""
        tool_calls_buffer = []
        tool_call_id = None
        tool_name = None
        tool_args = {}

        for chunk in llm_service.chat_completion(messages, stream=True, tools=tools):
            if not chunk.startswith('data: '):
                continue

            data_str = chunk[6:]
            if data_str == '[DONE]':
                break

            try:
                data = json.loads(data_str)
            except:
                continue

            if 'error' in data:
                yield f"data: {json.dumps({'error': data['error']})}\n\n"
                return

            if 'choices' in data and len(data['choices']) > 0:
                choice = data['choices'][0]
                delta = choice.get('delta', {})

                # 处理工具调用
                if 'tool_calls' in delta:
                    for tc in delta['tool_calls']:
                        if 'id' in tc:
                            tool_call_id = tc['id']
                        if 'function' in tc:
                            if 'name' in tc['function']:
                                tool_name = tc['function']['name']
                                yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'status': 'started'}})}\n\n"
                            if 'arguments' in tc['function']:
                                try:
                                    tool_args = json.loads(tc['function']['arguments'])
                                except:
                                    tool_args = {}

                # 处理普通内容
                content = delta.get('content', '')
                if content:
                    full_response += content
                    yield f"data: {json.dumps({'content': content})}\n\n"

        # 执行工具调用（如果有）
        if tool_name and tool_call_id:
            try:
                # 执行工具
                tool_result = tool_executor.execute(tool_name, tool_args, workspace)

                # 将工具结果添加到消息历史
                tool_message = {
                    'role': 'tool',
                    'content': json.dumps(tool_result, ensure_ascii=False),
                    'tool_call_id': tool_call_id
                }
                workspace.messages.append({'role': 'user', 'content': user_input})
                workspace.messages.append({'role': 'assistant', 'content': full_response, 'tool_calls': [{'id': tool_call_id, 'function': {'name': tool_name, 'arguments': json.dumps(tool_args)}}]})
                workspace.messages.append(tool_message)

                # 发送工具执行结果给前端
                yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'status': 'completed', 'result': tool_result}})}\n\n"

                # 如果工具是generate_exercise，需要特殊处理
                if tool_name == 'generate_exercise' and 'exercise' in tool_result:
                    yield f"data: {json.dumps({'exercise': tool_result['exercise']})}\n\n"

            except Exception as e:
                logger.error(f"工具执行失败: {str(e)}")
                yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'status': 'error', 'error': str(e)}})}\n\n"
        else:
            # 没有工具调用，正常保存消息
            workspace.messages.append({'role': 'user', 'content': user_input})
            workspace.messages.append({'role': 'assistant', 'content': full_response})
        
        # 更新token计数（估算）
        workspace.token_count = sum(len(m['content']) // 4 for m in workspace.messages)
        
        # 检查是否需要上下文压缩
        if workspace.token_count > workspace.token_threshold and not workspace.compressed_context:
            yield f"data: {json.dumps({'status': 'compressing_context'})}\n\n"
            summary = llm_service.compress_context(workspace.messages, study_plan, agent_state)
            workspace.compressed_context = summary
            yield f"data: {json.dumps({'status': 'context_compressed'})}\n\n"
        
        workspace_manager.save_workspace(workspace)
        
        yield f"data: {json.dumps({'done': True, 'token_count': workspace.token_count})}\n\n"
        yield "data: [DONE]\n\n"
    
    return Response(stream_with_context(generate()),
                   mimetype='text/event-stream',
                   headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/workspaces/<workspace_id>/messages', methods=['GET'])
def get_messages(workspace_id):
    """获取工作区消息历史"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    return jsonify({
        'success': True,
        'messages': workspace.messages,
        'phase': workspace.current_phase,
        'token_count': workspace.token_count,
        'token_threshold': workspace.token_threshold
    })

@app.route('/api/workspaces/<workspace_id>/files', methods=['GET'])
def get_files(workspace_id):
    """获取工作区文件列表"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    file_tree = workspace_manager.get_file_tree(workspace_id)
    return jsonify({'success': True, 'files': file_tree})

@app.route('/api/workspaces/<workspace_id>/files/<path:file_path>', methods=['GET'])
def read_file(workspace_id, file_path):
    """读取工作区文件"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    full_path = os.path.join(workspace.path, file_path)
    if not os.path.exists(full_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content, 'path': file_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/workspaces/<workspace_id>/export', methods=['GET'])
def export_conversation(workspace_id):
    """导出对话记录为JSON格式"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404

    # 构建完整的导出数据
    export_data = {
        'metadata': {
            'workspace_id': workspace.id,
            'theme': workspace.theme,
            'created_at': workspace.created_at,
            'current_phase': workspace.current_phase,
            'export_timestamp': datetime.now().isoformat(),
            'version': '1.0'
        },
        'conversation': workspace.messages,
        'study_plan': '',
        'files': []
    }

    # 读取学习计划
    study_plan_path = os.path.join(workspace.path, 'study_plan.md')
    if os.path.exists(study_plan_path):
        with open(study_plan_path, 'r', encoding='utf-8') as f:
            export_data['study_plan'] = f.read()

    # 获取文件列表
    file_tree = workspace_manager.get_file_tree(workspace_id)
    export_data['files'] = file_tree

    # 设置响应头，触发文件下载
    response = jsonify(export_data)
    response.headers['Content-Disposition'] = f'attachment; filename=conversation-{workspace_id}-{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    response.headers['Content-Type'] = 'application/json'

    return response

@app.route('/api/tools/execute', methods=['POST'])
def execute_tool():
    """执行工具"""
    data = request.json
    workspace_id = data.get('workspace_id')
    tool_name = data.get('tool')
    params = data.get('params', {})

    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404

    result = tool_executor.execute(tool_name, params, workspace)
    return jsonify(result)

@app.route('/api/exercises/<workspace_id>/<exercise_id>', methods=['GET'])
def get_exercise(workspace_id, exercise_id):
    """获取练习题"""
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    exercise_path = os.path.join(workspace.path, 'exercises', f"{exercise_id}.json")
    if not os.path.exists(exercise_path):
        return jsonify({'success': False, 'error': '练习题不存在'}), 404
    
    try:
        with open(exercise_path, 'r', encoding='utf-8') as f:
            exercise = json.load(f)
        return jsonify({'success': True, 'exercise': exercise})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/exercises/validate', methods=['POST'])
def validate_exercise():
    """验证练习题答案"""
    data = request.json
    exercise_id = data.get('exercise_id')
    workspace_id = data.get('workspace_id')
    answers = data.get('answers', [])
    
    workspace = workspace_manager.get_workspace(workspace_id)
    if not workspace:
        return jsonify({'success': False, 'error': '工作区不存在'}), 404
    
    exercise_path = os.path.join(workspace.path, 'exercises', f"{exercise_id}.json")
    if not os.path.exists(exercise_path):
        return jsonify({'success': False, 'error': '练习题不存在'}), 404
    
    try:
        with open(exercise_path, 'r', encoding='utf-8') as f:
            exercise = json.load(f)
        
        correct_answers = exercise.get('correct_answers', [])
        exercise_type = exercise.get('type', 'choice')
        
        # 客观题自动验证
        if exercise_type in ['choice', 'fill_blank', 'match', 'multi_fill']:
            is_correct = answers == correct_answers
            return jsonify({
                'success': True,
                'correct': is_correct,
                'correct_answers': correct_answers,
                'explanation': exercise.get('explanation', '')
            })
        else:
            # 主观题需要LLM批改
            return jsonify({
                'success': True,
                'requires_grading': True,
                'message': '主观题需要AI批改'
            })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 主入口 ====================

if __name__ == '__main__':
    # 检查配置文件
    if not os.path.exists(CONFIG_FILE):
        print("=" * 60)
        print("  配置文件不存在，请先运行配置向导")
        print("  python setup.py")
        print("=" * 60)
        sys.exit(1)
    
    print("=" * 60)
    print("  AI Learning Assistant 启动中...")
    print("=" * 60)
    print(f"  访问地址: http://localhost:5000")
    print(f"  工作区: {config_manager.get_workspace_root()}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
