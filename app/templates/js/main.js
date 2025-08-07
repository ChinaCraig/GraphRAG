/**
 * GraphRAG 前端主要JavaScript文件
 * 实现文档管理和智能检索功能
 */

class GraphRAGApp {
    constructor() {
        this.currentTab = 'document-management';
        this.currentPage = 1;
        this.pageSize = 20;
        this.searchKeyword = '';
        this.selectedFiles = new Set();
        this.uploadFiles = [];
        this.chatMessages = [];
        
        this.init();
    }

    /**
     * 初始化应用
     */
    init() {
        this.initEventListeners();
        this.loadFileList();
        this.setupWebSocket();
        
        // 启动进度监控（检查是否有未完成的处理任务）
        this.startProgressMonitoring();
    }

    /**
     * 初始化事件监听器
     */
    initEventListeners() {
        // 页签切换
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });

        // 文档管理相关事件
        this.initDocumentManagementEvents();
        
        // 智能检索相关事件
        this.initIntelligentSearchEvents();
        
        // 模态框事件
        this.initModalEvents();
        
        // 全局事件
        this.initGlobalEvents();
    }

    /**
     * 初始化文档管理事件
     */
    initDocumentManagementEvents() {
        // 上传按钮
        document.getElementById('uploadBtn').addEventListener('click', () => {
            this.showModal('uploadModal');
        });

        // 删除选中按钮
        document.getElementById('deleteSelectedBtn').addEventListener('click', () => {
            this.deleteSelectedFiles();
        });

        // 搜索
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.searchFiles();
        });

        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.searchFiles();
            }
        });

        // 全选
        document.getElementById('selectAll').addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });

        // 分页
        document.getElementById('prevPage').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadFileList();
            }
        });

        document.getElementById('nextPage').addEventListener('click', () => {
            this.currentPage++;
            this.loadFileList();
        });

        // 文件上传相关
        const fileInput = document.getElementById('fileInput');
        const dropZone = document.getElementById('dropZone');
        
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', this.handleDragOver.bind(this));
        dropZone.addEventListener('drop', this.handleDrop.bind(this));
        fileInput.addEventListener('change', this.handleFileSelect.bind(this));

        document.getElementById('confirmUpload').addEventListener('click', () => {
            this.startUpload();
        });
    }

    /**
     * 初始化智能检索事件
     */
    initIntelligentSearchEvents() {
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');

        sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });

        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 自动调整输入框高度
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
        });
    }

    /**
     * 初始化模态框事件
     */
    initModalEvents() {
        document.querySelectorAll('[data-close]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.hideModal(e.target.dataset.close);
            });
        });

        // 点击模态框外部关闭
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModal(modal.id);
                }
            });
        });
    }

    /**
     * 初始化全局事件
     */
    initGlobalEvents() {
        // ESC键关闭模态框
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                document.querySelectorAll('.modal.show').forEach(modal => {
                    this.hideModal(modal.id);
                });
            }
        });
    }

    /**
     * 切换页签
     */
    switchTab(tabName) {
        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

        // 更新内容显示
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tabName).classList.add('active');

        this.currentTab = tabName;

        // 根据页签执行特定操作
        if (tabName === 'document-management') {
            this.loadFileList();
        }
    }

    /**
     * 加载文件列表
     */
    async loadFileList() {
        this.showLoading();
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                page_size: this.pageSize
            });

            if (this.searchKeyword) {
                params.append('filename', this.searchKeyword);
            }

            const response = await fetch(`/api/file/list?${params}`);
            const data = await response.json();

            if (data.success) {
                this.renderFileList(data.data);
                this.updatePagination(data.data);
            } else {
                this.showToast('加载文件列表失败: ' + data.message, 'error');
            }
        } catch (error) {
            console.error('加载文件列表失败:', error);
            this.showToast('加载文件列表失败', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * 渲染文件列表
     */
    renderFileList(data) {
        const tbody = document.getElementById('fileTableBody');
        tbody.innerHTML = '';

        if (!data.files || data.files.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted">暂无文件</td>
                </tr>
            `;
            return;
        }

        data.files.forEach(file => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <input type="checkbox" value="${file.id}" class="file-checkbox">
                </td>
                <td>${file.id}</td>
                <td>${file.filename}</td>
                <td>${file.file_type.toUpperCase()}</td>
                <td class="file-size-cell">${this.formatFileSize(file.file_size)}</td>
                <td>${this.formatDateTime(file.upload_time)}</td>
                <td>
                    ${this.renderFileStatus(file)}
                </td>
                <td>${file.process_time ? this.formatDateTime(file.process_time) : '-'}</td>
                <td>
                    <div class="table-actions">
                        <button class="btn btn-secondary" onclick="app.viewFile(${file.id})" title="查看">
                            <svg class="icon" viewBox="0 0 24 24" fill="none">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="2"/>
                                <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>
                            </svg>
                        </button>
                        <button class="btn btn-danger" onclick="app.deleteFile(${file.id})" title="删除">
                            <svg class="icon" viewBox="0 0 24 24" fill="none">
                                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14z" stroke="currentColor" stroke-width="2"/>
                            </svg>
                        </button>
                    </div>
                </td>
            `;
            tbody.appendChild(row);
        });

        // 添加文件选择事件监听器
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.updateSelectedFiles();
            });
        });
    }

    /**
     * 更新分页信息
     */
    updatePagination(data) {
        const pageInfo = document.getElementById('pageInfo');
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');

        const totalPages = Math.ceil(data.total / this.pageSize);
        pageInfo.textContent = `第 ${this.currentPage} 页，共 ${totalPages} 页`;

        prevBtn.disabled = this.currentPage <= 1;
        nextBtn.disabled = this.currentPage >= totalPages;
    }

    /**
     * 搜索文件
     */
    searchFiles() {
        this.searchKeyword = document.getElementById('searchInput').value.trim();
        this.currentPage = 1;
        this.loadFileList();
    }

    /**
     * 切换全选状态
     */
    toggleSelectAll(checked) {
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
        });
        this.updateSelectedFiles();
    }

    /**
     * 更新选中文件状态
     */
    updateSelectedFiles() {
        this.selectedFiles.clear();
        document.querySelectorAll('.file-checkbox:checked').forEach(checkbox => {
            this.selectedFiles.add(parseInt(checkbox.value));
        });

        const deleteBtn = document.getElementById('deleteSelectedBtn');
        deleteBtn.disabled = this.selectedFiles.size === 0;

        // 更新全选按钮状态
        const allCheckboxes = document.querySelectorAll('.file-checkbox');
        const checkedCheckboxes = document.querySelectorAll('.file-checkbox:checked');
        const selectAllCheckbox = document.getElementById('selectAll');
        
        if (checkedCheckboxes.length === 0) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = false;
        } else if (checkedCheckboxes.length === allCheckboxes.length) {
            selectAllCheckbox.indeterminate = false;
            selectAllCheckbox.checked = true;
        } else {
            selectAllCheckbox.indeterminate = true;
        }
    }

    /**
     * 删除选中文件
     */
    async deleteSelectedFiles() {
        if (this.selectedFiles.size === 0) return;

        if (!confirm(`确定要删除选中的 ${this.selectedFiles.size} 个文件吗？`)) {
            return;
        }

        this.showLoading();

        try {
            const deletePromises = Array.from(this.selectedFiles).map(fileId => 
                fetch(`/api/file/${fileId}`, { method: 'DELETE' })
            );

            const responses = await Promise.all(deletePromises);
            const results = await Promise.all(responses.map(r => r.json()));

            const successCount = results.filter(r => r.success).length;
            const failCount = results.length - successCount;

            if (successCount > 0) {
                this.showToast(`成功删除 ${successCount} 个文件${failCount > 0 ? `，${failCount} 个文件删除失败` : ''}`, 
                             failCount > 0 ? 'warning' : 'success');
                this.loadFileList();
                this.selectedFiles.clear();
            } else {
                this.showToast('删除文件失败', 'error');
            }
        } catch (error) {
            console.error('删除文件失败:', error);
            this.showToast('删除文件失败', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * 删除单个文件
     */
    async deleteFile(fileId) {
        if (!confirm('确定要删除这个文件吗？')) {
            return;
        }

        this.showLoading();

        try {
            const response = await fetch(`/api/file/${fileId}`, { method: 'DELETE' });
            const data = await response.json();

            if (data.success) {
                this.showToast('文件删除成功', 'success');
                this.loadFileList();
            } else {
                this.showToast('删除失败: ' + data.message, 'error');
            }
        } catch (error) {
            console.error('删除文件失败:', error);
            this.showToast('删除文件失败', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * 查看文件
     */
    async viewFile(fileId) {
        this.showToast('文件查看功能开发中...', 'info');
    }

    /**
     * 处理拖拽悬停
     */
    handleDragOver(e) {
        e.preventDefault();
        e.currentTarget.classList.add('dragover');
    }

    /**
     * 处理文件拖拽
     */
    handleDrop(e) {
        e.preventDefault();
        e.currentTarget.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        this.addFilesToUpload(files);
    }

    /**
     * 处理文件选择
     */
    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        console.log('选择的文件:', files.map(f => ({ name: f.name, size: f.size, type: f.type })));
        this.addFilesToUpload(files);
    }

    /**
     * 添加文件到上传列表
     */
    addFilesToUpload(files) {
        console.log('添加文件到上传列表，原始文件数:', files.length);
        const validFiles = files.filter(file => this.validateFile(file));
        console.log('验证后的有效文件数:', validFiles.length);
        
        this.uploadFiles = [...this.uploadFiles, ...validFiles];
        console.log('当前上传列表文件数:', this.uploadFiles.length);
        
        this.renderUploadFileList();
        this.updateUploadButton();
    }

    /**
     * 验证文件
     */
    validateFile(file) {
        const allowedTypes = ['pdf', 'docx', 'doc', 'xlsx', 'xls', 'pptx', 'ppt', 'txt', 'md'];
        const fileExt = file.name.split('.').pop().toLowerCase();
        
        if (!allowedTypes.includes(fileExt)) {
            this.showToast(`不支持的文件类型: ${file.name}`, 'error');
            return false;
        }

        if (file.size > 104857600) { // 100MB
            this.showToast(`文件过大: ${file.name}`, 'error');
            return false;
        }

        return true;
    }

    /**
     * 渲染上传文件列表
     */
    renderUploadFileList() {
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';

        this.uploadFiles.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${this.formatFileSize(file.size)}</div>
                </div>
                <button class="remove-file" onclick="app.removeUploadFile(${index})">
                    <svg class="icon" viewBox="0 0 24 24" fill="none">
                        <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" stroke-width="2"/>
                        <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" stroke-width="2"/>
                    </svg>
                </button>
            `;
            fileList.appendChild(fileItem);
        });
    }

    /**
     * 移除上传文件
     */
    removeUploadFile(index) {
        this.uploadFiles.splice(index, 1);
        this.renderUploadFileList();
        this.updateUploadButton();
    }

    /**
     * 更新上传按钮状态
     */
    updateUploadButton() {
        const uploadBtn = document.getElementById('confirmUpload');
        uploadBtn.disabled = this.uploadFiles.length === 0;
    }

    /**
     * 开始上传
     */
    async startUpload() {
        console.log('开始上传，文件数量:', this.uploadFiles.length);
        console.log('上传文件列表:', this.uploadFiles.map(f => f.name));
        
        if (this.uploadFiles.length === 0) {
            console.log('没有文件可上传');
            this.showToast('请先选择要上传的文件', 'warning');
            return;
        }

        // 关闭上传模态框，回到文件列表
        this.hideModal('uploadModal');

        let completedFiles = 0;
        const totalFiles = this.uploadFiles.length;

        // 逐个上传文件
        for (const file of this.uploadFiles) {
            try {
                console.log(`正在上传文件: ${file.name}`);
                const result = await this.uploadSingleFile(file);
                console.log(`文件上传成功:`, result);
                completedFiles++;
                
                // 立即刷新文件列表，显示新上传的文件和进度
                this.loadFileList();
                
            } catch (error) {
                console.error('文件上传失败:', error);
                this.showToast(`文件上传失败: ${file.name} - ${error.message}`, 'error');
                continue;
            }
        }

        console.log(`所有文件上传完成，成功: ${completedFiles}/${totalFiles}`);
        
        // 清空上传文件列表
        this.uploadFiles = [];
        
        // 显示完成提示
        this.showToast(`文件上传完成，成功上传 ${completedFiles}/${totalFiles} 个文件`, 'success');
        
        // 启动进度监控
        this.startProgressMonitoring();
    }

    /**
     * 上传单个文件
     */
    async uploadSingleFile(file) {
        console.log(`uploadSingleFile 开始处理文件: ${file.name}, 大小: ${file.size}`);
        
        const formData = new FormData();
        formData.append('file', file);

        console.log('发送上传请求到:', '/api/file/upload');
        
        const response = await fetch('/api/file/upload', {
            method: 'POST',
            body: formData
        });

        console.log('上传响应状态:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('上传响应错误:', errorText);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        const data = await response.json();
        console.log('上传响应数据:', data);
        
        if (!data.success) {
            throw new Error(data.message);
        }

        return data;
    }

    /**
     * 启动进度监控
     */
    startProgressMonitoring() {
        // 定期刷新文件列表以显示最新的处理进度
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        this.progressInterval = setInterval(() => {
            // 检查是否有正在处理的文件
            this.checkProcessingFiles();
        }, 3000); // 每3秒刷新一次
    }

    /**
     * 检查处理中的文件
     */
    async checkProcessingFiles() {
        try {
            const response = await fetch(`/api/file/list?page=1&page_size=${this.pageSize}`);
            const data = await response.json();

            if (data.success && data.data.files) {
                const processingFiles = data.data.files.filter(file => 
                    this.isProcessingStatus(file.process_status)
                );

                // 如果没有处理中的文件，停止监控
                if (processingFiles.length === 0) {
                    this.stopProgressMonitoring();
                } else {
                    // 只更新列表，不显示加载指示器
                    this.renderFileList(data.data);
                }
            }
        } catch (error) {
            console.error('检查文件进度失败:', error);
        }
    }

    /**
     * 停止进度监控
     */
    stopProgressMonitoring() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
            this.progressInterval = null;
        }
        
        // 最终刷新一次列表
        this.loadFileList();
    }

    /**
     * 发送聊天消息
     */
    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();
        
        if (!message) return;

        // 添加用户消息
        this.addMessage('user', message);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // 显示打字指示器
        this.showTypingIndicator();

        try {
            // 调用智能检索API
            const response = await fetch('/api/search/qa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    question: message,
                    context_limit: 5
                })
            });

            const data = await response.json();
            
            this.hideTypingIndicator();

            if (data.success) {
                // 流式显示响应
                await this.streamMessage(data.data.answer || '抱歉，我无法理解您的问题。');
            } else {
                this.addMessage('assistant', '抱歉，查询失败：' + data.message);
            }
        } catch (error) {
            console.error('智能检索失败:', error);
            this.hideTypingIndicator();
            this.addMessage('assistant', '抱歉，服务暂时不可用，请稍后再试。');
        }
    }

    /**
     * 添加聊天消息
     */
    addMessage(role, content) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessageContent(content);
        
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return contentDiv;
    }

    /**
     * 流式显示消息
     */
    async streamMessage(content) {
        const messageDiv = this.addMessage('assistant', '');
        const contentDiv = messageDiv.querySelector('.message-content');
        
        // 模拟流式输出
        let index = 0;
        const streamInterval = setInterval(() => {
            if (index < content.length) {
                contentDiv.textContent += content[index];
                index++;
                
                // 滚动到底部
                document.getElementById('chatMessages').scrollTop = 
                    document.getElementById('chatMessages').scrollHeight;
            } else {
                clearInterval(streamInterval);
                // 格式化最终内容
                contentDiv.innerHTML = this.formatMessageContent(content);
            }
        }, 50);
    }

    /**
     * 格式化消息内容
     */
    formatMessageContent(content) {
        // 这里可以添加对图片、表格等的特殊处理
        // 目前只做基本的换行处理
        return content.replace(/\n/g, '<br>');
    }

    /**
     * 显示打字指示器
     */
    showTypingIndicator() {
        const chatMessages = document.getElementById('chatMessages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message assistant';
        typingDiv.id = 'typing-indicator';
        
        typingDiv.innerHTML = `
            <div class="message-content">
                <div class="typing-indicator">
                    <span>正在思考</span>
                    <div class="typing-dots">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        
        chatMessages.appendChild(typingDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * 隐藏打字指示器
     */
    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    /**
     * 设置WebSocket连接（用于实时进度更新）
     */
    setupWebSocket() {
        // WebSocket连接设置（可选功能）
        // 如果后端支持WebSocket，可以在这里建立连接
    }

    /**
     * 显示模态框
     */
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    /**
     * 隐藏模态框
     */
    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        modal.classList.remove('show');
        document.body.style.overflow = '';
        
        // 重置上传相关状态
        if (modalId === 'uploadModal') {
            this.uploadFiles = [];
            this.renderUploadFileList();
            this.updateUploadButton();
            document.getElementById('fileInput').value = '';
        }
    }

    /**
     * 显示加载指示器
     */
    showLoading() {
        document.getElementById('loadingIndicator').classList.add('show');
    }

    /**
     * 隐藏加载指示器
     */
    hideLoading() {
        document.getElementById('loadingIndicator').classList.remove('show');
    }

    /**
     * 显示提示消息
     */
    showToast(message, type = 'info') {
        // 简单的提示实现
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // 可以在这里实现更复杂的toast组件
        alert(message);
    }

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 格式化日期时间
     */
    formatDateTime(dateString) {
        if (!dateString) return '-';
        
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * 获取状态样式类
     */
    getStatusClass(status) {
        const statusMap = {
            'pending': 'pending',
            'uploading': 'processing',
            'extracting': 'processing',
            'vectorizing': 'processing',
            'graph_processing': 'processing',
            'completed': 'completed',
            'failed': 'failed',
            'extract_failed': 'failed',
            'vectorize_failed': 'failed',
            'graph_failed': 'failed',
            'process_failed': 'failed'
        };
        
        return statusMap[status] || 'pending';
    }

    /**
     * 获取状态显示文本
     */
    getStatusText(status) {
        const statusMap = {
            'pending': '待处理',
            'uploading': '上传中',
            'extracting': '提取中',
            'vectorizing': '向量化',
            'graph_processing': '图谱处理',
            'completed': '已完成',
            'failed': '失败',
            'extract_failed': '提取失败',
            'vectorize_failed': '向量化失败',
            'graph_failed': '图谱失败',
            'process_failed': '处理失败'
        };
        
        return statusMap[status] || status;
    }

    /**
     * 渲染文件状态（包括进度条）
     */
    renderFileStatus(file) {
        const status = file.process_status;
        const progressData = this.calculateFileProgress(status);
        
        // 如果是处理中的状态，显示进度条
        if (this.isProcessingStatus(status)) {
            return `
                <div class="file-progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progressData.progress}%"></div>
                    </div>
                    <div class="progress-text">
                        <span class="progress-percentage">${progressData.progress}%</span>
                        <span class="progress-stage">${progressData.stage_name}</span>
                    </div>
                </div>
            `;
        } else {
            // 其他状态显示徽章
            return `
                <span class="status-badge ${this.getStatusClass(status)}">
                    ${this.getStatusText(status)}
                </span>
            `;
        }
    }

    /**
     * 计算文件进度
     */
    calculateFileProgress(status) {
        const progressMap = {
            'pending': { progress: 10, stage_name: '文件已上传' },
            'extracting': { progress: 25, stage_name: '内容提取中' },
            'extracted': { progress: 40, stage_name: '内容提取完成' },
            'vectorizing': { progress: 55, stage_name: '向量化处理中' },
            'vectorized': { progress: 70, stage_name: '向量化完成' },
            'graph_processing': { progress: 85, stage_name: '知识图谱构建中' },
            'completed': { progress: 100, stage_name: '处理完成' }
        };
        
        return progressMap[status] || { progress: 0, stage_name: '未知状态' };
    }

    /**
     * 判断是否为处理中状态
     */
    isProcessingStatus(status) {
        const processingStatuses = ['pending', 'extracting', 'vectorizing', 'graph_processing'];
        return processingStatuses.includes(status);
    }
}

// 初始化应用
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new GraphRAGApp();
});