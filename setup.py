#!/usr/bin/env python3
"""
AI Learning Assistant - Interactive Configuration Wizard
交互式配置向导，支持首次运行配置和后续修改
"""

import os
import sys
import yaml
from typing import Dict, Any, Optional

CONFIG_FILE = "config.yml"

DEFAULT_CONFIG = {
    "llm": {
        "base_url": "",
        "api_key": "",
        "default_model": "",
        "temperature": 0.7,
        "models": []
    },
    "search": {
        "provider": "tavily",
        "api_key": "",
        "base_url": "",
        "categories": ["general"]
    },
    "workspace_root": "./workspaces"
}

PROVIDERS = {
    "1": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "models": ["gpt-4o", "gpt-5.2", "gpt-5-mini"]},
    "2": {"name": "Google (Gemini)", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "models": ["gemini-3-flash-preview", "gemini-3-pro-preview", "gemini-2.5-flash"]},
    "3": {"name": "Kimi (Moonshot)", "base_url": "https://api.moonshot.cn/v1", "models": ["kimi-k2.5", "kimi-k2"]},
    "4": {"name": "xAI (Grok)", "base_url": "https://api.x.ai/v1", "models": ["grok-4-1", "grok-4-1-fast"]},
    "5": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "models": ["deepseek-chat", "deepseek-reasoner"]},
    "6": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "models": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet", "google/gemini-3-pro"]},
    "7": {"name": "其他 (自定义)", "base_url": "", "models": []}
}

SEARCH_PROVIDERS = {
    "1": "tavily",
    "2": "jina",
    "3": "searxng",
    "4": "brave"
}


def print_header(title: str):
    """打印标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_section(title: str):
    """打印小节标题"""
    print(f"\n>>> {title}")


def get_input(prompt: str, default: Optional[str] = None, required: bool = False) -> str:
    """获取用户输入"""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        if value:
            return value
        elif default is not None:
            return default
        elif not required:
            return ""
        else:
            print("  [错误] 此项为必填项，请重新输入")


def get_choice(prompt: str, options: Dict[str, str], default: Optional[str] = None) -> str:
    """获取用户选择"""
    print(f"\n{prompt}")
    for key, value in options.items():
        marker = " *" if key == default else ""
        print(f"  [{key}] {value}{marker}")
    
    while True:
        choice = input(f"请选择 [默认: {default}]: ").strip() or default
        if choice in options:
            return choice
        print("  [错误] 无效选项，请重新选择")


def test_llm_connection(config: Dict[str, Any]) -> bool:
    """测试LLM连接"""
    import requests
    
    print("\n  正在测试LLM连接...")
    try:
        headers = {
            "Authorization": f"Bearer {config['llm']['api_key']}",
            "Content-Type": "application/json"
        }
        
        # 尝试使用chat completions接口
        response = requests.post(
            f"{config['llm']['base_url'].rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": config['llm']['default_model'],
                "messages": [{"role": "user", "content": 'Test. Just answer "OK". Do not answer anything else.'}],
                "max_tokens": 10
            },
            timeout=30
        )
        
        if response.status_code == 200:
            print("  [成功] LLM连接测试通过！")
            return True
        else:
            print(f"  [警告] 连接测试失败: HTTP {response.status_code}")
            print(f"  响应: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  [警告] 连接测试异常: {str(e)}")
        return False


def configure_llm(config: Dict[str, Any], is_first_run: bool) -> Dict[str, Any]:
    """配置LLM设置"""
    print_header("LLM 模型配置")
    
    print("\n请选择模型提供商:")
    for key, provider in PROVIDERS.items():
        print(f"  [{key}] {provider['name']}")
    
    choice = input("请选择 [1-7]: ").strip()
    if choice not in PROVIDERS:
        choice = "7"  # 默认其他
    
    provider = PROVIDERS[choice]
    print(f"\n已选择: {provider['name']}")
    
    # Base URL
    if provider['base_url'] and choice != "7":
        config['llm']['base_url'] = provider['base_url']
        print(f"  Base URL: {provider['base_url']}")
    else:
        config['llm']['base_url'] = get_input(
            "请输入API Base URL",
            default=config['llm'].get('base_url', ''),
            required=True
        )
    
    # API Key
    existing_key = config['llm'].get('api_key', '')
    masked_key = f"{existing_key[:8]}..." if existing_key and len(existing_key) > 10 else ""
    config['llm']['api_key'] = get_input(
        "请输入API Key",
        default=masked_key if not is_first_run else "",
        required=True
    )
    if config['llm']['api_key'] == masked_key:
        config['llm']['api_key'] = existing_key
    
    # Model
    if provider['models'] and choice != "7":
        print(f"\n推荐模型:")
        for i, model in enumerate(provider['models'], 1):
            print(f"  [{i}] {model}")
        print("  [0] 自定义输入")
        
        model_choice = input("请选择模型 [0]: ").strip() or "0"
        if model_choice != "0" and model_choice.isdigit():
            idx = int(model_choice) - 1
            if 0 <= idx < len(provider['models']):
                config['llm']['default_model'] = provider['models'][idx]
            else:
                config['llm']['default_model'] = get_input("请输入模型名称", required=True)
        else:
            config['llm']['default_model'] = get_input("请输入模型名称", required=True)
    else:
        config['llm']['default_model'] = get_input(
            "请输入模型名称",
            default=config['llm'].get('default_model', ''),
            required=True
        )
    
    # Temperature
    temp_str = get_input(
        "Temperature (0.0-2.0, 越低越确定)",
        default=str(config['llm'].get('temperature', 0.7))
    )
    try:
        config['llm']['temperature'] = float(temp_str)
    except ValueError:
        config['llm']['temperature'] = 0.7
    
    # Max Context
    max_context = get_input(
        "模型最大上下文长度 (K tokens)",
        default="128"
    )
    try:
        max_context_val = int(max_context)
    except ValueError:
        max_context_val = 128
    
    # 添加到models列表
    config['llm']['models'] = [{
        "name": config['llm']['default_model'],
        "max_context": max_context_val
    }]
    
    # 测试连接
    if config['llm']['api_key']:
        test_llm_connection(config)
    
    return config


def configure_search(config: Dict[str, Any], is_first_run: bool) -> Dict[str, Any]:
    """配置搜索设置"""
    print_header("搜索引擎配置 (可选)")
    
    print("\n支持的搜索提供商:")
    print("  [1] Tavily (推荐)")
    print("  [2] Jina AI")
    print("  [3] SearXNG (自建)")
    print("  [4] Brave Search")
    print("  [0] 跳过搜索配置")
    
    choice = input("请选择 [0]: ").strip() or "0"
    
    if choice == "0":
        config['search']['provider'] = ""
        print("  已跳过搜索配置")
        return config
    
    if choice in SEARCH_PROVIDERS:
        config['search']['provider'] = SEARCH_PROVIDERS[choice]
    else:
        config['search']['provider'] = "tavily"
    
    print(f"\n已选择: {config['search']['provider']}")
    
    # API Key (SearXNG不需要)
    if config['search']['provider'] != "searxng":
        existing_key = config['search'].get('api_key', '')
        masked_key = f"{existing_key[:8]}..." if existing_key and len(existing_key) > 10 else ""
        api_key = get_input(
            "请输入搜索API Key",
            default=masked_key if not is_first_run else "",
            required=False
        )
        if api_key == masked_key:
            pass  # 保持原值
        else:
            config['search']['api_key'] = api_key
    
    # SearXNG需要base_url
    if config['search']['provider'] == "searxng":
        config['search']['base_url'] = get_input(
            "SearXNG实例URL",
            default=config['search'].get('base_url', 'http://localhost:8080'),
            required=True
        )
    
    return config


def configure_workspace(config: Dict[str, Any]) -> Dict[str, Any]:
    """配置工作区"""
    print_header("工作区配置")
    
    config['workspace_root'] = get_input(
        "工作区根目录路径",
        default=config.get('workspace_root', './workspaces'),
        required=True
    )
    
    # 确保路径是相对或绝对路径
    if not config['workspace_root'].startswith(('./', '/', '~')):
        config['workspace_root'] = './' + config['workspace_root']
    
    return config


def save_config(config: Dict[str, Any]):
    """保存配置到文件"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"\n[成功] 配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print(f"\n[错误] 保存配置失败: {str(e)}")
        sys.exit(1)


def load_config() -> Dict[str, Any]:
    """加载现有配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or DEFAULT_CONFIG.copy()
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def show_current_config(config: Dict[str, Any]):
    """显示当前配置"""
    print_header("当前配置")
    
    llm = config.get('llm', {})
    search = config.get('search', {})
    
    print(f"\n[LLM配置]")
    print(f"  提供商: {llm.get('base_url', '未配置')}")
    api_key = llm.get('api_key', '')
    print(f"  API Key: {'*' * 10 if api_key else '未配置'}")
    print(f"  默认模型: {llm.get('default_model', '未配置')}")
    print(f"  Temperature: {llm.get('temperature', 0.7)}")
    
    print(f"\n[搜索配置]")
    print(f"  提供商: {search.get('provider', '未配置')}")
    search_key = search.get('api_key', '')
    print(f"  API Key: {'*' * 10 if search_key else '未配置'}")
    
    print(f"\n[工作区]")
    print(f"  根目录: {config.get('workspace_root', './workspaces')}")


def main():
    """主函数"""
    print_header("AI Learning Assistant - 配置向导")
    
    is_first_run = not os.path.exists(CONFIG_FILE)
    config = load_config()
    
    if is_first_run:
        print("\n欢迎使用 AI Learning Assistant!")
        print("这是您第一次运行，请完成以下配置。")
        
        # 完整配置流程
        config = configure_llm(config, is_first_run=True)
        config = configure_search(config, is_first_run=True)
        config = configure_workspace(config)
        
        save_config(config)
        
        print_header("配置完成")
        print(f"\n现在可以启动应用:")
        print(f"  python app.py")
        print(f"\n然后访问: http://localhost:5000")
        
    else:
        print("\n检测到已有配置文件。")
        show_current_config(config)
        
        print("\n选项:")
        print("  [1] 修改LLM配置")
        print("  [2] 修改搜索配置")
        print("  [3] 修改工作区配置")
        print("  [4] 重新配置全部")
        print("  [5] 测试LLM连接")
        print("  [0] 退出")
        
        choice = input("\n请选择 [0]: ").strip() or "0"
        
        if choice == "1":
            config = configure_llm(config, is_first_run=False)
            save_config(config)
        elif choice == "2":
            config = configure_search(config, is_first_run=False)
            save_config(config)
        elif choice == "3":
            config = configure_workspace(config)
            save_config(config)
        elif choice == "4":
            config = DEFAULT_CONFIG.copy()
            config = configure_llm(config, is_first_run=True)
            config = configure_search(config, is_first_run=True)
            config = configure_workspace(config)
            save_config(config)
        elif choice == "5":
            test_llm_connection(config)
        else:
            print("\n未做任何修改")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消配置")
        sys.exit(0)
