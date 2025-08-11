/**
 * GraphRAG 前端主要JavaScript文件
 * 实现文档管理和智能检索功能
 */

class GraphRAGApp {
    constructor() {
        this.currentTab = 'intelligent-search';
        this.currentPage = 1;
        this.pageSize = 20;
        this.searchKeyword = '';
        this.selectedFiles = new Set();
        this.uploadFiles = [];
        this.chatMessages = [];
        this.socket = null;
        this.isWebSocketConnected = false;
        this.fileRooms = new Set(); // 跟踪已加入的文件房间
        
        // 会话管理相关属性
        this.sessions = new Map(); // 存储所有会话
        this.currentSessionId = null;
        this.sessionIdCounter = 1;
        
        this.init();
    }

    /**
     * 初始化应用
     */
    init() {
        this.initEventListeners();
        
        // 🔧 修复：根据当前页签恢复状态，避免内容丢失
        if (this.currentTab === 'document-management') {
            this.restoreDocumentManagementState();
        } else {
            this.loadFileList();
        }
        
        this.setupWebSocket();
        
        // 🔧 修复：初始化会话管理功能
        this.initSessionManagement();
        
        // WebSocket连接是异步的，不要在这里立即检查连接状态
        // 定时任务的启动和停止将在WebSocket连接成功/失败的回调中处理
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
        
        // 确认删除事件
        this.initConfirmDeleteEvents();
        
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

        // 分页控制
        this.initPaginationEvents();

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
        // 🔧 修复：保存当前页签状态，避免内容丢失
        this.saveCurrentTabState();
        
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

        const previousTab = this.currentTab;
        this.currentTab = tabName;

        // 🔧 修复：根据页签恢复状态，避免重复加载
        if (tabName === 'document-management') {
            this.restoreDocumentManagementState();
        } else if (tabName === 'intelligent-search') {
            this.restoreIntelligentSearchState();
        }
        
        console.log(`🔄 页签切换: ${previousTab} → ${tabName}`);
    }

    /**
     * 保存当前页签状态
     */
    saveCurrentTabState() {
        try {
            if (this.currentTab === 'intelligent-search') {
                // 保存智能检索页签状态
                if (this.currentSessionId) {
                    this.saveCurrentSessionMessages();
                }
                
                // 保存会话管理状态到本地存储
                this.saveSessionsToStorage();
                
            } else if (this.currentTab === 'document-management') {
                // 保存文档管理页签状态
                const documentState = {
                    currentPage: this.currentPage,
                    pageSize: this.pageSize,
                    searchKeyword: this.searchKeyword,
                    selectedFiles: Array.from(this.selectedFiles),
                    lastLoadTime: Date.now()
                };
                
                localStorage.setItem('documentManagementState', JSON.stringify(documentState));
            }
            
            console.log(`💾 已保存 ${this.currentTab} 页签状态`);
            
        } catch (error) {
            console.error('保存页签状态失败:', error);
        }
    }

    /**
     * 恢复文档管理页签状态
     */
    restoreDocumentManagementState() {
        try {
            // 尝试从本地存储恢复状态
            const savedState = localStorage.getItem('documentManagementState');
            
            if (savedState) {
                const state = JSON.parse(savedState);
                
                // 检查状态是否过期（超过10分钟）
                const isExpired = Date.now() - state.lastLoadTime > 10 * 60 * 1000;
                
                if (!isExpired) {
                    // 恢复状态
                    this.currentPage = state.currentPage || 1;
                    this.pageSize = state.pageSize || 20;
                    this.searchKeyword = state.searchKeyword || '';
                    this.selectedFiles = new Set(state.selectedFiles || []);
                    
                    // 恢复搜索框内容
                    const searchInput = document.getElementById('searchInput');
                    if (searchInput) {
                        searchInput.value = this.searchKeyword;
                    }
                    
                    // 恢复页面大小选择
                    const pageSizeSelect = document.getElementById('pageSizeSelect');
                    if (pageSizeSelect) {
                        pageSizeSelect.value = this.pageSize;
                    }
                    
                    console.log('📄 已恢复文档管理页签状态');
                    
                    // 只有状态有效时才避免重新加载，直接加载文件列表以应用恢复的状态
                    this.loadFileList();
                    return;
                }
            }
            
            // 状态无效或不存在，正常加载
            this.loadFileList();
            
        } catch (error) {
            console.error('恢复文档管理状态失败:', error);
            // 出错时正常加载
            this.loadFileList();
        }
    }

    /**
     * 恢复智能检索页签状态
     */
    restoreIntelligentSearchState() {
        try {
            // 确保会话管理功能可用，但不强制创建新会话
            this.ensureSessionManagementReady(false);
            
            console.log('🤖 已恢复智能检索页签状态');
            
        } catch (error) {
            console.error('恢复智能检索状态失败:', error);
            // 出错时使用原有逻辑
            this.ensureSessionManagementReady();
        }
    }

    /**
     * 保存文档管理状态到本地存储
     */
    saveDocumentManagementState() {
        if (this.currentTab === 'document-management') {
            try {
                const documentState = {
                    currentPage: this.currentPage,
                    pageSize: this.pageSize,
                    searchKeyword: this.searchKeyword,
                    selectedFiles: Array.from(this.selectedFiles),
                    lastLoadTime: Date.now()
                };
                
                localStorage.setItem('documentManagementState', JSON.stringify(documentState));
                console.log('💾 文档管理状态已实时保存');
                
            } catch (error) {
                console.error('保存文档管理状态失败:', error);
            }
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
            row.setAttribute('data-file-id', file.id);
            row.innerHTML = `
                <td>
                    <input type="checkbox" value="${file.id}" class="file-checkbox">
                </td>
                <td>${file.id}</td>
                <td>${file.filename}</td>
                <td>${file.file_type.toUpperCase()}</td>
                <td class="file-size-cell">${this.formatFileSize(file.file_size)}</td>
                <td>${this.formatDateTime(file.upload_time)}</td>
                <td class="file-status-cell">
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
     * 初始化分页事件监听器
     */
    initPaginationEvents() {
        // 上一页按钮
        document.getElementById('prevPage').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.goToPage(this.currentPage - 1);
            }
        });

        // 下一页按钮
        document.getElementById('nextPage').addEventListener('click', () => {
            const totalPages = this.totalPages || 1;
            if (this.currentPage < totalPages) {
                this.goToPage(this.currentPage + 1);
            }
        });

        // 每页数量选择器
        document.getElementById('pageSizeSelect').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1; // 重置到第一页
            this.loadFileList();
            // 🔧 修复：实时保存页面大小设置
            this.saveDocumentManagementState();
        });
    }

    /**
     * 跳转到指定页面
     */
    goToPage(page) {
        this.currentPage = page;
        this.loadFileList();
        // 🔧 修复：实时保存翻页状态
        this.saveDocumentManagementState();
    }

    /**
     * 更新分页信息
     */
    updatePagination(data) {
        const pageInfo = document.getElementById('pageInfo');
        const totalPages = Math.ceil(data.total / this.pageSize);
        this.totalPages = totalPages; // 保存总页数

        // 更新信息显示（只显示总数）
        pageInfo.textContent = `共 ${data.total} 项`;

        // 更新按钮状态
        this.updatePaginationButtons(totalPages);

        // 更新每页数量选择器
        document.getElementById('pageSizeSelect').value = this.pageSize;
    }

    /**
     * 更新分页按钮状态
     */
    updatePaginationButtons(totalPages) {
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');

        // 上一页按钮
        prevBtn.disabled = this.currentPage <= 1;

        // 下一页按钮
        nextBtn.disabled = this.currentPage >= totalPages;
    }

    /**
     * 搜索文件
     */
    searchFiles() {
        this.searchKeyword = document.getElementById('searchInput').value.trim();
        this.currentPage = 1;
        this.loadFileList();
        // 🔧 修复：实时保存搜索状态
        this.saveDocumentManagementState();
    }

    /**
     * 切换全选状态
     */
    toggleSelectAll(checked) {
        document.querySelectorAll('.file-checkbox').forEach(checkbox => {
            checkbox.checked = checked;
        });
        this.updateSelectedFiles();
        // 🔧 修复：实时保存选择状态
        this.saveDocumentManagementState();
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
        // 控制按钮的显示/隐藏而不是启用/禁用
        if (this.selectedFiles.size === 0) {
            deleteBtn.style.display = 'none';
        } else {
            deleteBtn.style.display = 'inline-flex';
        }

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
        
        // 🔧 修复：实时保存文件选择状态
        this.saveDocumentManagementState();
    }

    /**
     * 删除选中文件
     */
    async deleteSelectedFiles() {
        if (this.selectedFiles.size === 0) return;

        // 使用新的确认删除模态框
        this.showConfirmDelete(
            `确定要删除选中的 ${this.selectedFiles.size} 个文件吗？`,
            () => this.executeDeleteSelectedFiles()
        );
    }

    /**
     * 执行删除选中文件
     */
    async executeDeleteSelectedFiles() {
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
                // 删除完成后隐藏删除选中按钮
                document.getElementById('deleteSelectedBtn').style.display = 'none';
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
        // 使用新的确认删除模态框
        this.showConfirmDelete(
            '确定要删除这个文件吗？',
            () => this.executeDeleteFile(fileId)
        );
    }

    /**
     * 执行删除单个文件
     */
    async executeDeleteFile(fileId) {
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
        try {
            console.log('🔍 开始预览文件，文件ID:', fileId);
            
            // 获取文件信息
            const fileInfoResponse = await fetch(`/api/file/${fileId}`);
            const fileInfoResult = await fileInfoResponse.json();
            
            if (!fileInfoResult.success) {
                throw new Error(fileInfoResult.message || '获取文件信息失败');
            }
            
            const fileInfo = fileInfoResult.data;
            const fileType = fileInfo.file_type?.toLowerCase();
            const fileName = fileInfo.filename;
            
            console.log('📄 文件信息:', { fileId, fileName, fileType });
            
            // 检查文件类型是否支持预览
            if (fileType !== 'pdf') {
                this.showToast(`暂不支持预览 ${fileType.toUpperCase()} 文件`, 'warning');
                return;
            }
            
            // 显示预览模态框
            this.showFilePreview(fileId, fileName, fileType);
            
        } catch (error) {
            console.error('❌ 文件预览失败:', error);
            this.showToast(`文件预览失败: ${error.message}`, 'error');
        }
    }

    /**
     * 显示文件预览模态框
     */
    async showFilePreview(fileId, fileName, fileType) {
        const modal = document.getElementById('filePreviewModal');
        const previewTitle = document.getElementById('previewTitle');
        const previewLoading = document.getElementById('previewLoading');
        const previewError = document.getElementById('previewError');
        const previewContainer = document.getElementById('previewContainer');
        const downloadBtn = document.getElementById('downloadBtn');
        
        // 设置标题和下载按钮
        previewTitle.textContent = `文件预览 - ${fileName}`;
        downloadBtn.onclick = () => this.downloadFile(fileId);
        
        // 显示模态框
        this.showModal('filePreviewModal');
        
        // 初始状态：显示加载，隐藏错误和内容
        previewLoading.style.display = 'flex';
        previewError.style.display = 'none';
        previewContainer.style.display = 'none';
        
        try {
            if (fileType === 'pdf') {
                await this.loadPdfPreview(fileId);
            } else {
                throw new Error(`不支持的文件类型: ${fileType}`);
            }
        } catch (error) {
            console.error('❌ 预览加载失败:', error);
            this.showPreviewError(error.message);
        }
    }

    /**
     * 加载PDF预览
     */
    async loadPdfPreview(fileId) {
        try {
            const previewLoading = document.getElementById('previewLoading');
            const previewContainer = document.getElementById('previewContainer');
            const pdfViewer = document.getElementById('pdfViewer');
            
            // 获取PDF文件流
            const pdfUrl = `/api/file/${fileId}/preview`;
            console.log('📖 正在加载PDF:', pdfUrl);
            
            // 初始化PDF.js
            if (typeof pdfjsLib === 'undefined') {
                throw new Error('PDF.js 库未加载');
            }
            
            // 设置PDF.js worker
            pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
            
            // 加载PDF文档
            const loadingTask = pdfjsLib.getDocument(pdfUrl);
            const pdf = await loadingTask.promise;
            
            console.log('✅ PDF加载成功，页数:', pdf.numPages);
            
            // 初始化PDF查看器状态
            this.pdfDocument = pdf;
            this.currentPdfPage = 1;
            this.pdfScale = 1.0;
            
            // 更新页面信息
            document.getElementById('pdfPageCount').textContent = pdf.numPages;
            document.getElementById('pdfPageNum').value = 1;
            document.getElementById('pdfPageNum').max = pdf.numPages;
            
            // 设置事件监听器
            this.setupPdfControls();
            
            // 渲染第一页
            await this.renderPdfPage(1);
            
            // 隐藏加载，显示PDF查看器
            previewLoading.style.display = 'none';
            previewContainer.style.display = 'block';
            pdfViewer.style.display = 'block';
            
        } catch (error) {
            console.error('❌ PDF加载失败:', error);
            throw error;
        }
    }

    /**
     * 设置PDF控制按钮事件
     */
    setupPdfControls() {
        const pdfPrevPage = document.getElementById('pdfPrevPage');
        const pdfNextPage = document.getElementById('pdfNextPage');
        const pdfPageNum = document.getElementById('pdfPageNum');
        const zoomIn = document.getElementById('zoomIn');
        const zoomOut = document.getElementById('zoomOut');
        const fitWidth = document.getElementById('fitWidth');
        
        // 移除旧的事件监听器（避免重复绑定）
        pdfPrevPage.replaceWith(pdfPrevPage.cloneNode(true));
        pdfNextPage.replaceWith(pdfNextPage.cloneNode(true));
        pdfPageNum.replaceWith(pdfPageNum.cloneNode(true));
        zoomIn.replaceWith(zoomIn.cloneNode(true));
        zoomOut.replaceWith(zoomOut.cloneNode(true));
        fitWidth.replaceWith(fitWidth.cloneNode(true));
        
        // 重新获取元素引用
        const newPdfPrevPage = document.getElementById('pdfPrevPage');
        const newPdfNextPage = document.getElementById('pdfNextPage');
        const newPdfPageNum = document.getElementById('pdfPageNum');
        const newZoomIn = document.getElementById('zoomIn');
        const newZoomOut = document.getElementById('zoomOut');
        const newFitWidth = document.getElementById('fitWidth');
        
        // 上一页
        newPdfPrevPage.addEventListener('click', () => {
            if (this.currentPdfPage > 1) {
                this.currentPdfPage--;
                newPdfPageNum.value = this.currentPdfPage;
                this.renderPdfPage(this.currentPdfPage);
            }
        });
        
        // 下一页
        newPdfNextPage.addEventListener('click', () => {
            if (this.currentPdfPage < this.pdfDocument.numPages) {
                this.currentPdfPage++;
                newPdfPageNum.value = this.currentPdfPage;
                this.renderPdfPage(this.currentPdfPage);
            }
        });
        
        // 页码输入
        newPdfPageNum.addEventListener('change', (e) => {
            const pageNum = parseInt(e.target.value);
            if (pageNum >= 1 && pageNum <= this.pdfDocument.numPages) {
                this.currentPdfPage = pageNum;
                this.renderPdfPage(this.currentPdfPage);
            } else {
                e.target.value = this.currentPdfPage;
            }
        });
        
        // 放大
        newZoomIn.addEventListener('click', () => {
            this.pdfScale = Math.min(this.pdfScale * 1.2, 3.0);
            this.renderPdfPage(this.currentPdfPage);
            this.updateZoomLevel();
        });
        
        // 缩小
        newZoomOut.addEventListener('click', () => {
            this.pdfScale = Math.max(this.pdfScale / 1.2, 0.5);
            this.renderPdfPage(this.currentPdfPage);
            this.updateZoomLevel();
        });
        
        // 适应宽度
        newFitWidth.addEventListener('click', () => {
            const container = document.getElementById('pdfCanvas');
            const containerWidth = container.clientWidth - 40; // 减去padding
            // 这个缩放值需要在渲染时计算，暂时设为1.0
            this.pdfScale = 1.0;
            this.renderPdfPage(this.currentPdfPage);
            this.updateZoomLevel();
        });
    }

    /**
     * 渲染PDF页面
     */
    async renderPdfPage(pageNum) {
        try {
            const page = await this.pdfDocument.getPage(pageNum);
            const canvas = document.getElementById('pdfCanvasElement');
            const context = canvas.getContext('2d');
            
            const viewport = page.getViewport({ scale: this.pdfScale });
            
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            
            await page.render(renderContext).promise;
            
            console.log(`📄 已渲染第 ${pageNum} 页`);
            
        } catch (error) {
            console.error('❌ 渲染PDF页面失败:', error);
            throw error;
        }
    }

    /**
     * 更新缩放级别显示
     */
    updateZoomLevel() {
        const zoomLevel = document.getElementById('zoomLevel');
        zoomLevel.textContent = `${Math.round(this.pdfScale * 100)}%`;
    }

    /**
     * 显示预览错误
     */
    showPreviewError(message) {
        const previewLoading = document.getElementById('previewLoading');
        const previewError = document.getElementById('previewError');
        const previewErrorMessage = document.getElementById('previewErrorMessage');
        const previewRetryBtn = document.getElementById('previewRetryBtn');
        
        previewLoading.style.display = 'none';
        previewError.style.display = 'flex';
        previewErrorMessage.textContent = message;
        
        // 重试按钮
        previewRetryBtn.onclick = () => {
            previewError.style.display = 'none';
            previewLoading.style.display = 'flex';
            // 这里可以重新调用预览逻辑
        };
    }

    /**
     * 下载文件
     */
    async downloadFile(fileId) {
        try {
            const downloadUrl = `/api/file/${fileId}/download`;
            console.log('⬇️ 正在下载文件:', downloadUrl);
            
            // 创建隐藏的下载链接
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showToast('文件下载已开始', 'success');
            
        } catch (error) {
            console.error('❌ 文件下载失败:', error);
            this.showToast(`文件下载失败: ${error.message}`, 'error');
        }
    }

    /* =================================================================== */
    /* 会话管理功能 */
    /* =================================================================== */

    /**
     * 初始化会话管理
     */
    initSessionManagement() {
        // 加载保存的会话
        this.loadSessionsFromStorage();
        
        // 如果没有会话，创建默认会话
        if (this.sessions.size === 0) {
            this.createNewSession();
        } else {
            // 激活第一个会话
            const firstSessionId = this.sessions.keys().next().value;
            this.switchToSession(firstSessionId);
        }
        
        // 初始化事件监听器
        this.initSessionEvents();
        
        // 更新会话列表显示
        this.updateSessionList();
        this.updateSessionStats();
    }

    /**
     * 初始化会话相关事件
     */
    initSessionEvents() {
        try {
            // 🔧 修复：添加错误处理和DOM元素检查
            
            // 新建会话按钮
            const newSessionBtn = document.getElementById('newSessionBtn');
            if (newSessionBtn) {
                newSessionBtn.addEventListener('click', () => {
                    this.createNewSession();
                });
                console.log('✅ 新建会话按钮事件已绑定');
            } else {
                console.error('❌ 未找到新建会话按钮元素 (newSessionBtn)');
            }

            // 清空所有会话按钮
            const clearAllBtn = document.getElementById('clearAllSessions');
            if (clearAllBtn) {
                clearAllBtn.addEventListener('click', () => {
                    this.showConfirmDialog(
                        '清空所有对话',
                        '此操作将永久删除所有对话历史，无法恢复。请谨慎操作！',
                        () => this.clearAllSessions(),
                        null,
                        '清空全部',
                        '取消',
                        true
                    );
                });
                console.log('✅ 清空所有会话按钮事件已绑定');
            } else {
                console.error('❌ 未找到清空所有会话按钮元素 (clearAllSessions)');
            }

            // 重命名当前会话按钮
            const renameBtn = document.getElementById('renameSessionBtn');
            if (renameBtn) {
                renameBtn.addEventListener('click', () => {
                    this.renameCurrentSession();
                });
                console.log('✅ 重命名会话按钮事件已绑定');
            } else {
                console.error('❌ 未找到重命名会话按钮元素 (renameSessionBtn)');
            }

            // 清空当前会话按钮
            const clearCurrentBtn = document.getElementById('clearCurrentSession');
            if (clearCurrentBtn) {
                clearCurrentBtn.addEventListener('click', () => {
                    this.showConfirmDialog(
                        '清空当前对话',
                        '此操作将永久删除当前对话的所有消息内容，无法恢复。确定要清空吗？',
                        () => this.clearCurrentSession(),
                        null,
                        '清空对话',
                        '取消',
                        true
                    );
                });
                console.log('✅ 清空当前会话按钮事件已绑定');
            } else {
                console.error('❌ 未找到清空当前会话按钮元素 (clearCurrentSession)');
            }
            
        } catch (error) {
            console.error('❌ 初始化会话事件时发生错误:', error);
        }
    }

    /**
     * 确保会话管理功能已准备就绪
     * 在切换到智能检索页签时调用
     * 
     * @param {boolean} forceCreateNew - 是否强制创建新会话，默认true
     */
    ensureSessionManagementReady(forceCreateNew = true) {
        try {
            // 检查关键DOM元素是否存在
            const newSessionBtn = document.getElementById('newSessionBtn');
            const sessionList = document.getElementById('sessionList');
            const chatMessages = document.getElementById('chatMessages');
            
            if (!newSessionBtn || !sessionList || !chatMessages) {
                console.warn('会话管理DOM元素未找到，等待DOM加载完成');
                return;
            }
            
            // 🔧 修复：根据参数决定是否强制创建新会话
            if (forceCreateNew && (!this.currentSessionId || this.sessions.size === 0)) {
                console.log('🔧 检测到无活跃会话，创建默认会话');
                this.createNewSession();
            } else if (!forceCreateNew) {
                // 不强制创建，只恢复现有状态
                console.log('🔄 恢复现有会话状态，不创建新会话');
            }
            
            // 更新UI显示
            this.updateSessionList();
            this.updateSessionStats();
            
            // 确保当前会话的UI状态正确
            if (this.currentSessionId && this.sessions.has(this.currentSessionId)) {
                const session = this.sessions.get(this.currentSessionId);
                this.updateCurrentSessionUI(session);
                this.loadSessionMessages(session);
            }
            
            console.log(`✅ 会话管理功能已准备就绪 (forceCreateNew: ${forceCreateNew})`);
            
        } catch (error) {
            console.error('确保会话管理就绪时发生错误:', error);
        }
    }

    /**
     * 创建新会话
     */
    createNewSession() {
        const sessionId = `session_${this.sessionIdCounter++}`;
        const session = {
            id: sessionId,
            title: `新对话 ${this.sessions.size + 1}`,
            messages: [],
            createdAt: new Date(),
            updatedAt: new Date()
        };
        
        this.sessions.set(sessionId, session);
        this.switchToSession(sessionId);
        this.updateSessionList();
        this.updateSessionStats();
        this.saveSessionsToStorage();
        
        console.log('🆕 创建新会话:', sessionId);
    }

    /**
     * 切换到指定会话
     */
    switchToSession(sessionId) {
        if (!this.sessions.has(sessionId)) {
            console.warn('会话不存在:', sessionId);
            return;
        }
        
        // 保存当前会话的消息到存储
        if (this.currentSessionId) {
            this.saveCurrentSessionMessages();
        }
        
        // 切换会话
        this.currentSessionId = sessionId;
        const session = this.sessions.get(sessionId);
        
        // 更新聊天消息显示
        this.loadSessionMessages(session);
        
        // 更新UI
        this.updateCurrentSessionUI(session);
        this.updateSessionList();
        this.saveSessionsToStorage();
        
        console.log('🔄 切换到会话:', sessionId);
    }

    /**
     * 删除会话
     */
    deleteSession(sessionId) {
        if (!this.sessions.has(sessionId)) {
            console.warn('尝试删除不存在的会话:', sessionId);
            return;
        }
        
        // 🔧 修复：如果删除的是当前会话，先清除当前会话ID，避免在已删除会话上操作
        const isCurrentSession = (this.currentSessionId === sessionId);
        
        if (isCurrentSession) {
            // 保存当前消息到会话中（在删除之前）
            const session = this.sessions.get(sessionId);
            if (session) {
                session.messages = [...this.chatMessages];
                session.updatedAt = new Date();
            }
            
            // 清除当前会话ID，避免后续操作尝试访问已删除的会话
            this.currentSessionId = null;
        }
        
        // 删除会话
        this.sessions.delete(sessionId);
        
        // 如果删除的是当前会话，切换到其他会话或创建新会话
        if (isCurrentSession) {
            if (this.sessions.size > 0) {
                const firstSessionId = this.sessions.keys().next().value;
                this.switchToSession(firstSessionId);
            } else {
                this.createNewSession();
            }
        }
        
        this.updateSessionList();
        this.updateSessionStats();
        this.saveSessionsToStorage();
        
        console.log('🗑️ 删除会话:', sessionId);
    }

    /**
     * 重命名当前会话
     */
    renameCurrentSession() {
        if (!this.currentSessionId) {
            console.warn('没有当前会话可重命名');
            return;
        }
        
        const session = this.sessions.get(this.currentSessionId);
        // 🔧 修复：检查会话是否存在
        if (!session) {
            console.warn('尝试重命名不存在的会话:', this.currentSessionId);
            return;
        }
        
        this.showInputDialog(
            '重命名对话',
            '请输入新的对话名称:',
            session.title,
            (newTitle) => {
                if (newTitle && newTitle.trim() !== '') {
                    session.title = newTitle.trim();
                    session.updatedAt = new Date();
                    this.updateCurrentSessionUI(session);
                    this.updateSessionList();
                    this.saveSessionsToStorage();
                    
                    console.log('✏️ 重命名会话:', this.currentSessionId, newTitle);
                }
            },
            null,
            '保存',
            '取消',
            '输入对话名称'
        );
    }

    /**
     * 清空当前会话
     */
    clearCurrentSession() {
        if (!this.currentSessionId) {
            console.warn('没有当前会话可清空');
            return;
        }
        
        const session = this.sessions.get(this.currentSessionId);
        // 🔧 修复：检查会话是否存在
        if (!session) {
            console.warn('尝试清空不存在的会话:', this.currentSessionId);
            return;
        }
        
        session.messages = [];
        session.updatedAt = new Date();
        
        // 清空聊天界面
        this.clearChatMessages();
        this.updateSessionList();
        this.saveSessionsToStorage();
        
        console.log('🧹 清空会话:', this.currentSessionId);
    }

    /**
     * 清空所有会话
     */
    clearAllSessions() {
        this.sessions.clear();
        this.currentSessionId = null;
        this.sessionIdCounter = 1;
        
        // 创建新的默认会话
        this.createNewSession();
        
        console.log('🧹 清空所有会话');
    }

    /**
     * 加载会话消息到聊天界面
     */
    loadSessionMessages(session) {
        this.clearChatMessages();
        
        if (session.messages.length === 0) {
            // 显示欢迎消息
            this.showWelcomeMessage();
        } else {
            // 加载历史消息
            session.messages.forEach(message => {
                this.addMessageToChat(message);
            });
        }
    }

    /**
     * 保存当前会话的消息
     */
    saveCurrentSessionMessages() {
        if (!this.currentSessionId) {
            return;
        }
        
        const session = this.sessions.get(this.currentSessionId);
        // 🔧 修复：检查会话是否存在，防止在已删除的会话上操作
        if (!session) {
            console.warn('尝试保存消息到不存在的会话:', this.currentSessionId);
            return;
        }
        
        // 🔧 修复：只有当消息内容真正发生变化时才更新时间
        const currentMessages = [...this.chatMessages];
        const hasContentChanged = this.hasMessagesChanged(session.messages, currentMessages);
        
        session.messages = currentMessages;
        
        // 只有在内容真正变化时才更新updatedAt时间
        if (hasContentChanged) {
            session.updatedAt = new Date();
            console.log('💬 会话内容已更新，更新时间戳:', this.currentSessionId);
        } else {
            console.log('👀 会话内容无变化，保持原更新时间:', this.currentSessionId);
        }
    }

    /**
     * 检查消息内容是否发生变化
     */
    hasMessagesChanged(oldMessages, newMessages) {
        // 如果数量不同，肯定有变化
        if (!oldMessages || oldMessages.length !== newMessages.length) {
            return true;
        }
        
        // 比较每条消息的内容和角色
        for (let i = 0; i < oldMessages.length; i++) {
            const oldMsg = oldMessages[i];
            const newMsg = newMessages[i];
            
            // 检查关键属性是否有变化
            if (oldMsg.role !== newMsg.role || 
                oldMsg.content !== newMsg.content ||
                oldMsg.timestamp !== newMsg.timestamp) {
                return true;
            }
        }
        
        // 所有消息都相同
        return false;
    }

    /**
     * 更新当前会话的UI显示
     */
    updateCurrentSessionUI(session) {
        // 🔧 修复：检查session是否存在
        if (!session) {
            console.warn('尝试更新不存在的会话UI');
            // 设置默认显示
            document.getElementById('currentSessionTitle').textContent = '新对话';
            document.getElementById('currentSessionTime').textContent = '';
            return;
        }
        
        const titleElement = document.getElementById('currentSessionTitle');
        const timeElement = document.getElementById('currentSessionTime');
        
        if (titleElement) {
            titleElement.textContent = session.title;
        }
        if (timeElement) {
            timeElement.textContent = this.formatSessionTime(session.updatedAt);
        }
    }

    /**
     * 更新会话列表显示
     */
    updateSessionList() {
        const sessionList = document.getElementById('sessionList');
        sessionList.innerHTML = '';
        
        // 按更新时间排序会话
        const sortedSessions = Array.from(this.sessions.values()).sort((a, b) => 
            new Date(b.updatedAt) - new Date(a.updatedAt)
        );
        
        sortedSessions.forEach(session => {
            const sessionElement = this.createSessionElement(session);
            sessionList.appendChild(sessionElement);
        });
    }

    /**
     * 创建会话元素
     */
    createSessionElement(session) {
        const div = document.createElement('div');
        div.className = `session-item ${session.id === this.currentSessionId ? 'active' : ''}`;
        div.dataset.sessionId = session.id;
        
        div.innerHTML = `
            <div class="session-content">
                <div class="session-title">${this.escapeHtml(session.title)}</div>
                <div class="session-meta">
                    <span class="session-message-count">
                        <svg class="icon" viewBox="0 0 24 24" fill="none" style="width: 12px; height: 12px;">
                            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        ${session.messages.length}
                    </span>
                    <span>${this.formatSessionTime(session.updatedAt)}</span>
                </div>
            </div>
            <div class="session-actions">
                <button class="session-action-btn" onclick="app.renameSession('${session.id}')" title="重命名">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" style="width: 14px; height: 14px;">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
                <button class="session-action-btn" onclick="app.confirmDeleteSession('${session.id}')" title="删除">
                    <svg class="icon" viewBox="0 0 24 24" fill="none" style="width: 14px; height: 14px;">
                        <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
        `;
        
        // 添加点击事件
        div.addEventListener('click', (e) => {
            if (!e.target.closest('.session-actions')) {
                this.switchToSession(session.id);
            }
        });
        
        return div;
    }

    /**
     * 重命名会话（通过会话ID）
     */
    renameSession(sessionId) {
        const session = this.sessions.get(sessionId);
        if (!session) return;
        
        this.showInputDialog(
            '重命名对话',
            '请输入新的对话名称:',
            session.title,
            (newTitle) => {
                if (newTitle && newTitle.trim() !== '') {
                    session.title = newTitle.trim();
                    session.updatedAt = new Date();
                    
                    if (sessionId === this.currentSessionId) {
                        this.updateCurrentSessionUI(session);
                    }
                    
                    this.updateSessionList();
                    this.saveSessionsToStorage();
                }
            },
            null,
            '保存',
            '取消',
            '输入对话名称'
        );
    }

    /**
     * 确认删除会话
     */
    confirmDeleteSession(sessionId) {
        const session = this.sessions.get(sessionId);
        if (!session) return;
        
        this.showConfirmDialog(
            '删除对话',
            `确定要删除对话 "${session.title}" 吗？\n\n此操作将永久删除该对话的所有消息记录，无法恢复。`,
            () => this.deleteSession(sessionId),
            null,
            '删除对话',
            '取消',
            true
        );
    }

    /**
     * 更新会话统计
     */
    updateSessionStats() {
        const sessionCount = this.sessions.size;
        document.getElementById('sessionCount').textContent = `总对话: ${sessionCount}`;
    }

    /**
     * 格式化会话时间
     */
    formatSessionTime(date) {
        const now = new Date();
        const sessionDate = new Date(date);
        const diffInMinutes = Math.floor((now - sessionDate) / (1000 * 60));
        
        if (diffInMinutes < 1) {
            return '刚刚';
        } else if (diffInMinutes < 60) {
            return `${diffInMinutes}分钟前`;
        } else if (diffInMinutes < 24 * 60) {
            const hours = Math.floor(diffInMinutes / 60);
            return `${hours}小时前`;
        } else {
            const days = Math.floor(diffInMinutes / (24 * 60));
            if (days < 7) {
                return `${days}天前`;
            } else {
                return sessionDate.toLocaleDateString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit'
                });
            }
        }
    }

    /**
     * 清空聊天消息
     */
    clearChatMessages() {
        this.chatMessages = [];
        const chatMessagesContainer = document.getElementById('chatMessages');
        chatMessagesContainer.innerHTML = '';
    }

    /**
     * 显示欢迎消息
     */
    showWelcomeMessage() {
        const chatMessagesContainer = document.getElementById('chatMessages');
        chatMessagesContainer.innerHTML = `
            <div class="welcome-message">
                <h2>欢迎使用智能检索</h2>
                <p>您可以输入问题，系统会分析并返回相关的完整内容，包括文本、图表、图片、表格等。</p>
                <div class="welcome-features">
                    <div class="feature-item">
                        <svg class="icon" viewBox="0 0 24 24" fill="none">
                            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" fill="currentColor"/>
                        </svg>
                        <span>智能语义理解</span>
                    </div>
                    <div class="feature-item">
                        <svg class="icon" viewBox="0 0 24 24" fill="none">
                            <path d="M9 12l2 2 4-4M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9 9 4.03 9 9z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        <span>多模态内容检索</span>
                    </div>
                    <div class="feature-item">
                        <svg class="icon" viewBox="0 0 24 24" fill="none">
                            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" fill="currentColor"/>
                        </svg>
                        <span>实时知识图谱分析</span>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 添加消息到聊天界面（用于加载历史消息）
     */
    addMessageToChat(message) {
        this.addMessage(message.role, message.content, message.multimodalContent);
    }

    /**
     * 更新会话状态（发送消息后调用）
     */
    updateSessionAfterMessage() {
        if (!this.currentSessionId) return;
        
        const session = this.sessions.get(this.currentSessionId);
        if (!session) return;
        
        // 更新会话时间
        session.updatedAt = new Date();
        
        // 如果是第一条消息，基于消息内容更新会话标题
        if (session.messages.length === 0 && this.chatMessages.length > 0) {
            const firstUserMessage = this.chatMessages.find(m => m.role === 'user');
            if (firstUserMessage) {
                session.title = this.truncateTitle(firstUserMessage.content);
            }
        }
        
        // 保存消息到会话
        this.saveCurrentSessionMessages();
        
        // 更新UI
        this.updateCurrentSessionUI(session);
        this.updateSessionList();
        this.updateSessionStats();
        this.saveSessionsToStorage();
    }

    /**
     * 截断标题到合适长度
     */
    truncateTitle(text) {
        const maxLength = 30;
        if (text.length <= maxLength) {
            return text;
        }
        return text.substring(0, maxLength) + '...';
    }

    /**
     * 保存会话到本地存储
     */
    saveSessionsToStorage() {
        try {
            const sessionsData = {
                sessions: Array.from(this.sessions.entries()),
                currentSessionId: this.currentSessionId,
                sessionIdCounter: this.sessionIdCounter
            };
            localStorage.setItem('graphrag_sessions', JSON.stringify(sessionsData));
        } catch (error) {
            console.warn('保存会话到本地存储失败:', error);
        }
    }

    /**
     * 从本地存储加载会话
     */
    loadSessionsFromStorage() {
        try {
            const savedData = localStorage.getItem('graphrag_sessions');
            if (savedData) {
                const sessionsData = JSON.parse(savedData);
                this.sessions = new Map(sessionsData.sessions || []);
                this.currentSessionId = sessionsData.currentSessionId;
                this.sessionIdCounter = sessionsData.sessionIdCounter || 1;
            }
        } catch (error) {
            console.warn('从本地存储加载会话失败:', error);
            this.sessions = new Map();
            this.currentSessionId = null;
            this.sessionIdCounter = 1;
        }
    }

    /**
     * 显示确认对话框
     */
    showConfirmDialog(title, message, onConfirm, onCancel = null, confirmText = '确认', cancelText = '取消', isDestructive = false) {
        this.createConfirmModal(title, message, onConfirm, onCancel, confirmText, cancelText, isDestructive);
    }

    /**
     * 创建确认模态框
     */
    createConfirmModal(title, message, onConfirm, onCancel, confirmText, cancelText, isDestructive) {
        // 创建模态框HTML
        const modalHTML = `
            <div id="customConfirmModal" class="modal show">
                <div class="modal-content confirm-modal">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="close-btn" onclick="app.hideConfirmModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="color: var(--text-secondary); line-height: 1.6; margin: 0;">${message.replace(/\n/g, '<br>')}</p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="app.hideConfirmModal('cancel')">${cancelText}</button>
                        <button class="btn ${isDestructive ? 'btn-danger' : 'btn-primary'}" onclick="app.hideConfirmModal('confirm')">${confirmText}</button>
                    </div>
                </div>
            </div>
        `;

        // 添加到页面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // 存储回调函数
        this._confirmModalCallbacks = { onConfirm, onCancel };
        
        // 添加键盘事件监听
        document.addEventListener('keydown', this.handleConfirmModalKeydown.bind(this));
        
        // 添加点击背景关闭功能
        const modal = document.getElementById('customConfirmModal');
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideConfirmModal('cancel');
            }
        });
    }

    /**
     * 隐藏确认模态框
     */
    hideConfirmModal(action = 'cancel') {
        const modal = document.getElementById('customConfirmModal');
        if (!modal) return;
        
        // 移除键盘事件监听
        document.removeEventListener('keydown', this.handleConfirmModalKeydown.bind(this));
        
        // 执行回调
        if (action === 'confirm' && this._confirmModalCallbacks?.onConfirm) {
            this._confirmModalCallbacks.onConfirm();
        } else if (action === 'cancel' && this._confirmModalCallbacks?.onCancel) {
            this._confirmModalCallbacks.onCancel();
        }
        
        // 移除模态框
        modal.remove();
        this._confirmModalCallbacks = null;
    }

    /**
     * 处理确认模态框键盘事件
     */
    handleConfirmModalKeydown(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            this.hideConfirmModal('cancel');
        } else if (e.key === 'Enter') {
            e.preventDefault();
            this.hideConfirmModal('confirm');
        }
    }

    /**
     * 显示输入对话框
     */
    showInputDialog(title, message, defaultValue = '', onConfirm, onCancel = null, confirmText = '确认', cancelText = '取消', placeholder = '') {
        this.createInputModal(title, message, defaultValue, onConfirm, onCancel, confirmText, cancelText, placeholder);
    }

    /**
     * 创建输入模态框
     */
    createInputModal(title, message, defaultValue, onConfirm, onCancel, confirmText, cancelText, placeholder) {
        // 创建模态框HTML
        const modalHTML = `
            <div id="customInputModal" class="modal show">
                <div class="modal-content confirm-modal">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="close-btn" onclick="app.hideInputModal()">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="color: var(--text-secondary); line-height: 1.6; margin: 0 0 var(--spacing-lg) 0;">${message}</p>
                        <input 
                            type="text" 
                            id="customInputValue" 
                            value="${this.escapeHtml(defaultValue)}" 
                            placeholder="${this.escapeHtml(placeholder)}"
                            style="
                                width: 100%;
                                padding: var(--spacing-sm) var(--spacing-md);
                                border: 1px solid var(--border-color);
                                border-radius: var(--radius-md);
                                background: var(--bg-secondary);
                                color: var(--text-primary);
                                font-size: var(--font-size-base);
                                font-family: var(--font-family);
                                outline: none;
                                transition: border-color 0.2s ease;
                            "
                            onfocus="this.style.borderColor = 'var(--accent-primary)'"
                            onblur="this.style.borderColor = 'var(--border-color)'"
                        />
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="app.hideInputModal('cancel')">${cancelText}</button>
                        <button class="btn btn-primary" onclick="app.hideInputModal('confirm')">${confirmText}</button>
                    </div>
                </div>
            </div>
        `;

        // 添加到页面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // 存储回调函数
        this._inputModalCallbacks = { onConfirm, onCancel };
        
        // 聚焦并选中输入框
        setTimeout(() => {
            const input = document.getElementById('customInputValue');
            if (input) {
                input.focus();
                input.select();
            }
        }, 100);
        
        // 添加键盘事件监听
        document.addEventListener('keydown', this.handleInputModalKeydown.bind(this));
        
        // 添加点击背景关闭功能
        const modal = document.getElementById('customInputModal');
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideInputModal('cancel');
            }
        });
    }

    /**
     * 隐藏输入模态框
     */
    hideInputModal(action = 'cancel') {
        const modal = document.getElementById('customInputModal');
        if (!modal) return;
        
        // 移除键盘事件监听
        document.removeEventListener('keydown', this.handleInputModalKeydown.bind(this));
        
        // 获取输入值
        const input = document.getElementById('customInputValue');
        const value = input ? input.value.trim() : '';
        
        // 执行回调
        if (action === 'confirm' && this._inputModalCallbacks?.onConfirm) {
            this._inputModalCallbacks.onConfirm(value);
        } else if (action === 'cancel' && this._inputModalCallbacks?.onCancel) {
            this._inputModalCallbacks.onCancel();
        }
        
        // 移除模态框
        modal.remove();
        this._inputModalCallbacks = null;
    }

    /**
     * 处理输入模态框键盘事件
     */
    handleInputModalKeydown(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            this.hideInputModal('cancel');
        } else if (e.key === 'Enter') {
            e.preventDefault();
            this.hideInputModal('confirm');
        }
    }

    /**
     * HTML转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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

        // 🔧 修复：先保存要上传的文件列表，避免在hideModal中被清空
        const filesToUpload = [...this.uploadFiles];
        const totalFiles = filesToUpload.length;

        // 关闭上传模态框，回到文件列表
        this.hideModal('uploadModal');

        let completedFiles = 0;

        // 逐个上传文件
        for (const file of filesToUpload) {
            try {
                console.log(`正在上传文件: ${file.name}`);
                const result = await this.uploadSingleFile(file);
                console.log(`文件上传成功:`, result);
                completedFiles++;
                
                // 如果有文件ID且WebSocket已连接，加入文件房间监听进度
                const fileId = result.data?.file_id;
                if (fileId) {
                    console.log('📤 文件上传成功，文件ID:', fileId);
                    console.log('🔌 WebSocket连接状态:', this.isWebSocketConnected);
                    if (this.isWebSocketConnected) {
                        this.joinFileRoom(fileId);
                    } else {
                        console.log('⚠️ WebSocket未连接，无法加入房间，将使用定时刷新模式');
                    }
                } else {
                    console.error('❌ 上传结果中没有文件ID:', result);
                    console.error('完整响应结构:', JSON.stringify(result, null, 2));
                }
                
                // 立即刷新文件列表，显示新上传的文件和进度
                this.loadFileList();
                
            } catch (error) {
                console.error('文件上传失败:', error);
                this.showToast(`文件上传失败: ${file.name} - ${error.message}`, 'error');
                continue;
            }
        }

        console.log(`所有文件上传完成，成功: ${completedFiles}/${totalFiles}`);
        
        // 显示完成提示 (已注释掉alert提示)
        // this.showToast(`文件上传完成，成功上传 ${completedFiles}/${totalFiles} 个文件`, 'success');
        
        // 如果WebSocket未连接，启动进度监控作为备选方案
        if (!this.isWebSocketConnected) {
        this.startProgressMonitoring();
        }
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
        // 只有在WebSocket未连接时才启动定时监控
        if (this.isWebSocketConnected) {
            console.log('WebSocket已连接，跳过定时监控启动');
            return;
        }
        
        // 定期刷新文件列表以显示最新的处理进度
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        console.log('启动定时进度监控（WebSocket备选方案）');
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
            console.log('定时进度监控已停止');
        }
    }

    /**
     * 发送聊天消息
     */
    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();
        
        if (!message) return;

        // 确保有当前会话
        if (!this.currentSessionId) {
            this.createNewSession();
        }

        // 添加用户消息
        this.addMessage('user', message);
        chatInput.value = '';
        chatInput.style.height = 'auto';
        
        // 更新会话状态
        this.updateSessionAfterMessage();

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
                // 🎯 流式显示响应，支持多模态内容
                const answer = data.data.answer || '抱歉，我无法理解您的问题。';
                const multimodalContent = data.data.multimodal_content || null;
                await this.streamMessage(answer, multimodalContent);
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
     * 添加聊天消息 - 支持多模态内容
     */
    addMessage(role, content, multimodalContent = null) {
        // 创建消息对象
        const messageObj = {
            id: Date.now() + Math.random(),
            role: role,
            content: content,
            multimodalContent: multimodalContent,
            timestamp: new Date()
        };
        
        // 添加到当前消息数组
        this.chatMessages.push(messageObj);
        
        // 如果不是欢迎消息，保存到当前会话
        if (this.currentSessionId && this.chatMessages.length > 0) {
            // 清除欢迎消息如果存在
            const chatMessagesContainer = document.getElementById('chatMessages');
            const welcomeMessage = chatMessagesContainer.querySelector('.welcome-message');
            if (welcomeMessage) {
                welcomeMessage.remove();
            }
        }
        
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        messageDiv.dataset.messageId = messageObj.id;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessageContent(content, multimodalContent);
        
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return contentDiv;
    }

    /**
     * 流式显示消息 - 支持多模态内容渐进渲染
     */
    async streamMessage(content, multimodalContent = null) {
        // 🎯 创建消息容器，但不立即添加多模态内容
        const contentDiv = this.addMessage('assistant', '');
        
        // 🔤 第一阶段：流式显示文本内容
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
                
                // 🎯 文本显示完成后，开始渐进渲染多模态内容
                this.progressiveRenderMultimodal(contentDiv, content, multimodalContent);
            }
        }, 50);
    }

    /**
     * 渐进式渲染多模态内容
     */
    async progressiveRenderMultimodal(contentDiv, textContent, multimodalContent) {
        // 先更新文本内容的格式
        contentDiv.innerHTML = this.formatMessageContent(textContent);
        
        if (!multimodalContent) return;
        
        // 🎯 创建多模态内容容器
        const multimodalContainer = document.createElement('div');
        multimodalContainer.className = 'multimodal-content streaming';
        contentDiv.appendChild(multimodalContainer);
        
        // 🖼️ 渐进渲染图片
        if (multimodalContent.images && multimodalContent.images.length > 0) {
            await this.streamRenderImages(multimodalContainer, multimodalContent.images);
        }
        
        // 📊 渐进渲染表格
        if (multimodalContent.tables && multimodalContent.tables.length > 0) {
            await this.streamRenderTables(multimodalContainer, multimodalContent.tables);
        }
        
        // 📈 渐进渲染图表
        if (multimodalContent.charts && multimodalContent.charts.length > 0) {
            await this.streamRenderCharts(multimodalContainer, multimodalContent.charts);
        }
        
        // 移除流式加载标识
        multimodalContainer.classList.remove('streaming');
    }
    
    /**
     * 流式渲染图片
     */
    async streamRenderImages(container, images) {
        for (let i = 0; i < images.length; i++) {
            const img = images[i];
            const imagePath = img.file_path || img.path || '';
            const description = img.description || img.text || `图片 ${i + 1}`;
            const elementId = img.element_id || `img_${i}`;
            
            // 创建图片容器
            const imageItem = document.createElement('div');
            imageItem.className = 'multimodal-item image-item fade-in';
            imageItem.setAttribute('data-element-id', elementId);
            
            imageItem.innerHTML = `
                <div class="multimodal-header">
                    <span class="multimodal-type">🖼️ 图片</span>
                    <span class="multimodal-id">${elementId}</span>
                </div>
                ${imagePath ? `
                    <div class="image-container">
                        <img src="${imagePath}" alt="${description}" class="multimodal-image" 
                             onerror="this.style.display='none'" onload="this.parentNode.querySelector('.image-placeholder').style.display='none'">
                        <div class="image-placeholder">📷 图片加载中...</div>
                    </div>
                ` : ''}
                ${description ? `<div class="multimodal-description">${description}</div>` : ''}
            `;
            
            container.appendChild(imageItem);
            
            // 滚动到底部
            this.scrollToBottom();
            
            // 等待一段时间再渲染下一个
            await this.delay(300);
        }
    }
    
    /**
     * 流式渲染表格
     */
    async streamRenderTables(container, tables) {
        for (let i = 0; i < tables.length; i++) {
            const table = tables[i];
            const title = table.title || `表格 ${i + 1}`;
            const elementId = table.element_id || `table_${i}`;
            const summary = table.summary || '';
            
            let tableHtml = '';
            if (table.table_data && Array.isArray(table.table_data)) {
                tableHtml = this.generateTableHtml(table.table_data);
            } else if (table.content) {
                tableHtml = `<div class="table-content">${table.content}</div>`;
            }
            
            const tableItem = document.createElement('div');
            tableItem.className = 'multimodal-item table-item fade-in';
            tableItem.setAttribute('data-element-id', elementId);
            
            tableItem.innerHTML = `
                <div class="multimodal-header">
                    <span class="multimodal-type">📊 表格</span>
                    <span class="multimodal-id">${elementId}</span>
                </div>
                <div class="table-title">${title}</div>
                ${summary ? `<div class="table-summary">${summary}</div>` : ''}
                <div class="table-container">
                    ${tableHtml}
                </div>
            `;
            
            container.appendChild(tableItem);
            
            // 滚动到底部
            this.scrollToBottom();
            
            // 等待一段时间再渲染下一个
            await this.delay(400);
        }
    }
    
    /**
     * 流式渲染图表
     */
    async streamRenderCharts(container, charts) {
        for (let i = 0; i < charts.length; i++) {
            const chart = charts[i];
            const description = chart.description || `图表 ${i + 1}`;
            const elementId = chart.element_id || `chart_${i}`;
            
            const chartItem = document.createElement('div');
            chartItem.className = 'multimodal-item chart-item fade-in';
            chartItem.setAttribute('data-element-id', elementId);
            
            chartItem.innerHTML = `
                <div class="multimodal-header">
                    <span class="multimodal-type">📈 图表</span>
                    <span class="multimodal-id">${elementId}</span>
                </div>
                <div class="chart-description">${description}</div>
            `;
            
            container.appendChild(chartItem);
            
            // 滚动到底部
            this.scrollToBottom();
            
            // 等待一段时间再渲染下一个
            await this.delay(300);
        }
    }
    
    /**
     * 延迟函数
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * 滚动到底部
     */
    scrollToBottom() {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    /**
     * 格式化消息内容 - 支持多模态内容渲染
     */
    formatMessageContent(content, multimodalContent = null) {
        // 基本的换行处理
        let formattedContent = content.replace(/\n/g, '<br>');
        
        // 🎯 处理多模态内容
        if (multimodalContent) {
            const multimodalElements = this.renderMultimodalContent(multimodalContent);
            if (multimodalElements) {
                formattedContent += multimodalElements;
            }
        }
        
        // 🔍 处理内容中的特殊标记（支持内联多模态引用）
        formattedContent = this.processInlineReferences(formattedContent);
        
        return formattedContent;
    }
    
    /**
     * 渲染多模态内容
     */
    renderMultimodalContent(multimodalContent) {
        let elements = [];
        
        // 🖼️ 渲染图片
        if (multimodalContent.images && multimodalContent.images.length > 0) {
            elements.push(this.renderImages(multimodalContent.images));
        }
        
        // 📊 渲染表格
        if (multimodalContent.tables && multimodalContent.tables.length > 0) {
            elements.push(this.renderTables(multimodalContent.tables));
        }
        
        // 📈 渲染图表
        if (multimodalContent.charts && multimodalContent.charts.length > 0) {
            elements.push(this.renderCharts(multimodalContent.charts));
        }
        
        return elements.length > 0 ? `<div class="multimodal-content">${elements.join('')}</div>` : '';
    }
    
    /**
     * 渲染图片内容
     */
    renderImages(images) {
        const imageElements = images.map((img, index) => {
            const imagePath = img.file_path || img.path || '';
            const description = img.description || img.text || `图片 ${index + 1}`;
            const elementId = img.element_id || `img_${index}`;
            
            return `
                <div class="multimodal-item image-item" data-element-id="${elementId}">
                    <div class="multimodal-header">
                        <span class="multimodal-type">🖼️ 图片</span>
                        <span class="multimodal-id">${elementId}</span>
                    </div>
                    ${imagePath ? `
                        <div class="image-container">
                            <img src="${imagePath}" alt="${description}" class="multimodal-image" 
                                 onerror="this.style.display='none'" onload="this.parentNode.querySelector('.image-placeholder').style.display='none'">
                            <div class="image-placeholder">📷 图片加载中...</div>
                        </div>
                    ` : ''}
                    ${description ? `<div class="multimodal-description">${description}</div>` : ''}
                </div>
            `;
        }).join('');
        
        return imageElements;
    }
    
    /**
     * 渲染表格内容
     */
    renderTables(tables) {
        const tableElements = tables.map((table, index) => {
            const title = table.title || `表格 ${index + 1}`;
            const elementId = table.element_id || `table_${index}`;
            const summary = table.summary || '';
            
            let tableHtml = '';
            if (table.table_data && Array.isArray(table.table_data)) {
                tableHtml = this.generateTableHtml(table.table_data);
            } else if (table.content) {
                tableHtml = `<div class="table-content">${table.content}</div>`;
            }
            
            return `
                <div class="multimodal-item table-item" data-element-id="${elementId}">
                    <div class="multimodal-header">
                        <span class="multimodal-type">📊 表格</span>
                        <span class="multimodal-id">${elementId}</span>
                    </div>
                    <div class="table-title">${title}</div>
                    ${summary ? `<div class="table-summary">${summary}</div>` : ''}
                    <div class="table-container">
                        ${tableHtml}
                    </div>
                </div>
            `;
        }).join('');
        
        return tableElements;
    }
    
    /**
     * 渲染图表内容
     */
    renderCharts(charts) {
        const chartElements = charts.map((chart, index) => {
            const description = chart.description || `图表 ${index + 1}`;
            const elementId = chart.element_id || `chart_${index}`;
            
            return `
                <div class="multimodal-item chart-item" data-element-id="${elementId}">
                    <div class="multimodal-header">
                        <span class="multimodal-type">📈 图表</span>
                        <span class="multimodal-id">${elementId}</span>
                    </div>
                    <div class="chart-description">${description}</div>
                </div>
            `;
        }).join('');
        
        return chartElements;
    }
    
    /**
     * 生成表格HTML
     */
    generateTableHtml(tableData) {
        if (!tableData || tableData.length === 0) return '';
        
        let html = '<table class="multimodal-table">';
        
        // 表头
        if (tableData.length > 0) {
            html += '<thead><tr>';
            Object.keys(tableData[0]).forEach(key => {
                html += `<th>${key}</th>`;
            });
            html += '</tr></thead>';
        }
        
        // 表体
        html += '<tbody>';
        tableData.forEach(row => {
            html += '<tr>';
            Object.values(row).forEach(value => {
                html += `<td>${value || ''}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        
        return html;
    }
    
    /**
     * 处理内联引用
     */
    processInlineReferences(content) {
        // 处理图片引用: [图片:element_id]
        content = content.replace(/\[图片:([^\]]+)\]/g, '<span class="inline-reference image-ref" data-element-id="$1">🖼️ $1</span>');
        
        // 处理表格引用: [表格:element_id]
        content = content.replace(/\[表格:([^\]]+)\]/g, '<span class="inline-reference table-ref" data-element-id="$1">📊 $1</span>');
        
        // 处理图表引用: [图表:element_id]
        content = content.replace(/\[图表:([^\]]+)\]/g, '<span class="inline-reference chart-ref" data-element-id="$1">📈 $1</span>');
        
        return content;
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
        console.log('🔌 开始初始化WebSocket连接...');
        try {
            // 动态加载Socket.IO库
            console.log('📦 开始加载Socket.IO库...');
            this.loadSocketIO().then(() => {
                console.log('✅ Socket.IO库加载成功，开始建立连接...');
                // 连接到WebSocket服务器
                this.socket = io({
                    transports: ['websocket', 'polling']
                });
                
                // 连接成功
                this.socket.on('connect', () => {
                    console.log('✅ WebSocket连接成功，Socket ID:', this.socket.id);
                    this.isWebSocketConnected = true;
                    
                    // WebSocket连接成功，停止定时刷新
                    this.stopProgressMonitoring();
                    
                    // 加入正在处理的文件房间
                    this.joinProcessingFileRooms();
                });
                
                // 连接错误
                this.socket.on('connect_error', (error) => {
                    console.error('WebSocket连接失败:', error);
                    this.isWebSocketConnected = false;
                    
                    // WebSocket连接失败，启动定时刷新作为备选方案
                    this.startProgressMonitoring();
                });
                
                // 断开连接
                this.socket.on('disconnect', (reason) => {
                    console.log('WebSocket断开连接:', reason);
                    this.isWebSocketConnected = false;
                    
                    // WebSocket断开，启动定时刷新作为备选方案
                    this.startProgressMonitoring();
                });
                
                // 监听文件进度更新
                this.socket.on('file_progress', (data) => {
                    console.log('📊 收到文件进度更新:', data);
                    this.handleFileProgressUpdate(data);
                });
                
                // 监听文件完成通知
                this.socket.on('file_completed', (data) => {
                    this.handleFileCompleted(data);
                });
                
                // 监听文件列表更新通知
                this.socket.on('file_list_update', () => {
                    console.log('🔄 收到文件列表更新通知');
                    this.loadFileList();
                });
                
                // 监听房间加入成功事件
                this.socket.on('joined_room', (data) => {
                    console.log('🏠 成功加入房间:', data);
                });
                
                // 监听连接状态事件
                this.socket.on('status', (data) => {
                    console.log('📡 连接状态:', data);
                });
                
                // 监听错误事件
                this.socket.on('error', (data) => {
                    console.error('❌ WebSocket错误:', data);
                });
                
                // 注意：这里不要设置isWebSocketConnected = true
                // 实际的连接状态将在connect事件中设置
                
            }).catch(error => {
                console.error('❌ 加载Socket.IO失败:', error);
                this.isWebSocketConnected = false;
                // 回退到定时刷新模式
                console.log('🔄 回退到定时刷新模式');
                this.startProgressMonitoring();
            });
            
        } catch (error) {
            console.error('❌ WebSocket初始化失败:', error);
            this.isWebSocketConnected = false;
            // 回退到定时刷新模式
            console.log('🔄 回退到定时刷新模式');
            this.startProgressMonitoring();
        }
    }

    /**
     * 动态加载Socket.IO库
     */
    async loadSocketIO() {
        return new Promise((resolve, reject) => {
            // 检查是否已经加载了Socket.IO
            if (typeof io !== 'undefined') {
                console.log('✅ Socket.IO已存在，无需重复加载');
                resolve();
                return;
            }
            
            // 动态创建script标签加载Socket.IO
            const script = document.createElement('script');
            script.src = 'https://cdn.socket.io/4.7.2/socket.io.min.js';
            script.onload = () => {
                console.log('Socket.IO库加载成功');
                resolve();
            };
            script.onerror = () => {
                reject(new Error('Socket.IO库加载失败'));
            };
            document.head.appendChild(script);
        });
    }

    /**
     * 处理文件进度更新
     */
    handleFileProgressUpdate(data) {
        console.log('收到文件进度更新:', data);
        
        // 更新文件列表中对应文件的进度显示
        const fileId = data.file_id;
        const fileRow = document.querySelector(`tr[data-file-id="${fileId}"]`);
        
        if (fileRow) {
            // 找到状态列并更新进度条
            const statusCell = fileRow.querySelector('.file-status-cell');
            if (statusCell) {
                statusCell.innerHTML = this.renderFileProgressFromData(data);
                
                // 如果进度达到100%，延迟2秒后刷新文件列表以显示最终状态
                if (data.progress >= 100) {
                    setTimeout(() => {
                        this.loadFileList();
                    }, 2000);
                }
            }
        }
    }

    /**
     * 处理文件完成通知
     */
    handleFileCompleted(data) {
        console.log('收到文件完成通知:', data);
        
        // 显示完成提示
        const message = data.success ? '文件处理完成' : data.message || '文件处理失败';
        const type = data.success ? 'success' : 'error';
        this.showToast(message, type);
        
        // 离开文件房间
        this.leaveFileRoom(data.file_id);
        
        // 刷新文件列表
        this.loadFileList();
    }

    /**
     * 根据WebSocket数据渲染文件进度
     */
    renderFileProgressFromData(data) {
        const status = data.status;
        const progress = data.progress || 0;
        const stageName = data.stage_name || '处理中';
        
        // 如果是处理中的状态或者有明确的进度值，显示进度条
        if (this.isProcessingStatus(status) || (progress > 0 && progress <= 100)) {
            return `
                <div class="file-progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                    <div class="progress-text">
                        <span class="progress-percentage">${progress}%</span>
                        <span class="progress-stage">${stageName}</span>
                    </div>
                </div>
            `;
        } else {
            // 显示状态标签
            return this.renderStatusBadge(status);
        }
    }

    /**
     * 渲染状态徽章
     */
    renderStatusBadge(status) {
        return `
            <span class="status-badge ${this.getStatusClass(status)}">
                ${this.getStatusText(status)}
            </span>
        `;
    }

    /**
     * 加入文件房间
     */
    joinFileRoom(fileId) {
        if (this.socket && this.isWebSocketConnected && !this.fileRooms.has(fileId)) {
            console.log(`🚪 尝试加入文件房间: file_${fileId}`);
            this.socket.emit('join_file_room', { file_id: fileId });
            this.fileRooms.add(fileId);
            console.log(`✅ 已发送加入房间请求: file_${fileId}`);
        } else {
            console.log('⚠️ 无法加入文件房间:', {
                hasSocket: !!this.socket,
                isConnected: this.isWebSocketConnected,
                alreadyInRoom: this.fileRooms.has(fileId),
                fileId: fileId
            });
        }
    }

    /**
     * 离开文件房间
     */
    leaveFileRoom(fileId) {
        if (this.socket && this.isWebSocketConnected && this.fileRooms.has(fileId)) {
            this.socket.emit('leave_file_room', { file_id: fileId });
            this.fileRooms.delete(fileId);
            console.log(`离开文件房间: file_${fileId}`);
        }
    }

    /**
     * 加入正在处理的文件房间
     */
    async joinProcessingFileRooms() {
        try {
            // 获取当前文件列表，找出正在处理的文件
            const response = await fetch('/api/file/list');
            const data = await response.json();
            
            if (data.success && data.data.files) {
                data.data.files.forEach(file => {
                    if (this.isProcessingStatus(file.process_status)) {
                        this.joinFileRoom(file.id);
                    }
                });
            }
        } catch (error) {
            console.error('获取文件列表失败:', error);
        }
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
     * 显示确认删除模态框
     */
    showConfirmDelete(message, onConfirm) {
        const messageElement = document.getElementById('confirmDeleteMessage');
        messageElement.textContent = message;
        
        // 存储确认回调函数
        this.deleteConfirmCallback = onConfirm;
        
        this.showModal('confirmDeleteModal');
    }

    /**
     * 初始化确认删除模态框事件
     */
    initConfirmDeleteEvents() {
        // 取消删除
        document.getElementById('cancelDelete').addEventListener('click', () => {
            this.hideModal('confirmDeleteModal');
            this.deleteConfirmCallback = null;
        });

        // 确认删除
        document.getElementById('confirmDeleteAction').addEventListener('click', () => {
            if (this.deleteConfirmCallback) {
                this.deleteConfirmCallback();
                this.deleteConfirmCallback = null;
            }
            this.hideModal('confirmDeleteModal');
        });

        // 点击模态框背景关闭
        document.getElementById('confirmDeleteModal').addEventListener('click', (e) => {
            if (e.target.id === 'confirmDeleteModal') {
                this.hideModal('confirmDeleteModal');
                this.deleteConfirmCallback = null;
            }
        });
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
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        const container = document.getElementById('toastContainer');
        
        // 创建toast元素
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        // 获取对应类型的图标
        const icon = this.getToastIcon(type);
        
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">${message}</div>
            <button class="toast-close" type="button">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        `;
        
        // 添加到容器
        container.appendChild(toast);
        
        // 添加关闭事件
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            this.hideToast(toast);
        });
        
        // 显示动画
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        // 自动关闭
        setTimeout(() => {
            this.hideToast(toast);
        }, type === 'error' ? 6000 : 4000); // 错误消息显示更久
    }

    /**
     * 获取Toast图标
     */
    getToastIcon(type) {
        const icons = {
            success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20,6 9,17 4,12"></polyline>
                      </svg>`,
            error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="15" y1="9" x2="9" y2="15"></line>
                      <line x1="9" y1="9" x2="15" y2="15"></line>
                    </svg>`,
            warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                      </svg>`,
            info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                     <circle cx="12" cy="12" r="10"></circle>
                     <line x1="12" y1="16" x2="12" y2="12"></line>
                     <line x1="12" y1="8" x2="12.01" y2="8"></line>
                   </svg>`
        };
        return icons[type] || icons.info;
    }

    /**
     * 隐藏Toast
     */
    hideToast(toast) {
        if (!toast || !toast.parentNode) return;
        
        toast.classList.remove('show');
        
        // 等待动画完成后移除元素
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
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
        
        try {
            let date;
            
            // 如果时间字符串没有时区信息，假设它是中国时间（UTC+8）
            if (dateString.indexOf('T') !== -1 && 
                dateString.indexOf('+') === -1 && 
                dateString.indexOf('Z') === -1) {
                // 添加中国时区标识
                date = new Date(dateString + '+08:00');
            } else {
                date = new Date(dateString);
            }
            
            // 检查日期是否有效
            if (isNaN(date.getTime())) {
                console.warn('无效的日期字符串:', dateString);
                return dateString;
            }
            
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Asia/Shanghai'  // 明确指定中国时区
        });
        } catch (error) {
            console.error('日期格式化失败:', error, '原始字符串:', dateString);
            return dateString;
        }
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