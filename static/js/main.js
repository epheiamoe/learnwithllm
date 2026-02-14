/**
 * AI Learning Assistant - 主JavaScript文件
 * 包含全局工具函数和共享功能
 */

// 主题管理
const ThemeManager = {
    init() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggle());
        }
    },
    
    toggle() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    },
    
    get() {
        return document.documentElement.getAttribute('data-theme');
    }
};

// 通知系统
const NotificationManager = {
    container: null,
    
    init() {
        this.container = document.getElementById('notification-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'notification-container';
            this.container.className = 'notification-container';
            document.body.appendChild(this.container);
        }
    },
    
    show(message, type = 'info', duration = 3000) {
        if (!this.container) this.init();
        
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-message">${this.escapeHtml(message)}</span>
            <button class="notification-close" onclick="this.parentElement.remove()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        `;
        
        this.container.appendChild(notification);
        
        // 触发动画
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });
        
        // 自动移除
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }
        
        return notification;
    },
    
    success(message, duration) {
        return this.show(message, 'success', duration);
    },
    
    error(message, duration) {
        return this.show(message, 'error', duration);
    },
    
    warning(message, duration) {
        return this.show(message, 'warning', duration);
    },
    
    info(message, duration) {
        return this.show(message, 'info', duration);
    },
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// 加载管理器
const LoadingManager = {
    overlay: null,
    
    init() {
        this.overlay = document.getElementById('loading-overlay');
    },
    
    show(text = '处理中...') {
        if (!this.overlay) this.init();
        if (this.overlay) {
            const textEl = this.overlay.querySelector('.loading-text');
            if (textEl) textEl.textContent = text;
            this.overlay.classList.remove('hidden');
        }
    },
    
    hide() {
        if (this.overlay) {
            this.overlay.classList.add('hidden');
        }
    }
};

// API 请求工具
const API = {
    baseUrl: '',
    
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        if (options.body && typeof options.body === 'object') {
            mergedOptions.body = JSON.stringify(options.body);
        }
        
        try {
            const response = await fetch(this.baseUrl + url, mergedOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    },
    
    get(url) {
        return this.request(url, { method: 'GET' });
    },
    
    post(url, body) {
        return this.request(url, { method: 'POST', body });
    },
    
    delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
};

// 流式请求工具
const StreamingAPI = {
    async* stream(url, options = {}) {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr === '[DONE]') return;
                        
                        try {
                            const data = JSON.parse(dataStr);
                            yield data;
                        } catch (e) {
                            console.warn('解析SSE数据失败:', e);
                        }
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }
};

// Markdown 渲染器
const MarkdownRenderer = {
    render(content) {
        if (!content) return '';
        
        let html = this.escapeHtml(content);
        
        // 代码块
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
            return `<div class="code-block">
                <div class="code-header">
                    <span class="code-lang">${lang || 'text'}</span>
                    <button class="code-copy-btn" onclick="MarkdownRenderer.copyCode(this)">复制</button>
                </div>
                <pre><code>${this.escapeHtml(code.trim())}</code></pre>
            </div>`;
        });
        
        // 行内代码
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        
        // 粗体
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        
        // 斜体
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
        
        // 标题
        html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
        html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
        html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
        
        // 列表
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
        
        // 换行
        html = html.replace(/\n/g, '<br>');
        
        // 隐藏工具调用标签
        html = html.replace(/<tool_call>[\s\S]*?<\/tool_call>/g, '');
        
        return html;
    },
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    copyCode(btn) {
        const code = btn.closest('.code-block').querySelector('code').innerText;
        navigator.clipboard.writeText(code).then(() => {
            btn.textContent = '已复制';
            setTimeout(() => btn.textContent = '复制', 2000);
        });
    }
};

// 模态框管理器
const ModalManager = {
    modals: new Map(),
    
    init() {
        // 点击遮罩关闭
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal-overlay')) {
                const modal = e.target.closest('.modal');
                if (modal) this.close(modal.id);
            }
        });
        
        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeAll();
            }
        });
    },
    
    open(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            this.modals.set(id, modal);
        }
    },
    
    close(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('active');
            this.modals.delete(id);
            
            if (this.modals.size === 0) {
                document.body.style.overflow = '';
            }
        }
    },
    
    closeAll() {
        this.modals.forEach((modal, id) => {
            this.close(id);
        });
    },
    
    toggle(id) {
        const modal = document.getElementById(id);
        if (modal) {
            if (modal.classList.contains('active')) {
                this.close(id);
            } else {
                this.open(id);
            }
        }
    }
};

// 本地存储工具
const Storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) {
            console.error('存储失败:', e);
            return false;
        }
    },
    
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.error('读取失败:', e);
            return defaultValue;
        }
    },
    
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (e) {
            console.error('删除失败:', e);
            return false;
        }
    },
    
    clear() {
        try {
            localStorage.clear();
            return true;
        } catch (e) {
            console.error('清空失败:', e);
            return false;
        }
    }
};

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 节流函数
function throttle(func, limit) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func(...args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// 格式化日期
function formatDate(dateStr, options = {}) {
    const date = new Date(dateStr);
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return date.toLocaleDateString('zh-CN', { ...defaultOptions, ...options });
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    ThemeManager.init();
    NotificationManager.init();
    LoadingManager.init();
    ModalManager.init();
});

// 导出全局函数
window.ThemeManager = ThemeManager;
window.NotificationManager = NotificationManager;
window.LoadingManager = LoadingManager;
window.API = API;
window.StreamingAPI = StreamingAPI;
window.MarkdownRenderer = MarkdownRenderer;
window.ModalManager = ModalManager;
window.Storage = Storage;
window.debounce = debounce;
window.throttle = throttle;
window.formatDate = formatDate;
window.formatFileSize = formatFileSize;
