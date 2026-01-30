// ===== State =====
let currentOrder = null;
let currentUser = null;
let userRole = null; // 'QC', 'Packing', 'Shipout', 'Admin', etc.
let isLoggedIn = false;
let cameraEnabled = true;
let recordingLimit = 300; // Default 5 minutes
let autoRecordEnabled = true;
let selectedCameraIndex = 0;
let selectedPrinter = null; // Selected printer for Shipout role

// Packing mode state
let packingPendingItems = []; // Items scanned but not yet confirmed
let packingOrderId = null;

// Shipout mode state
let shipoutPendingItems = []; // Items scanned but not yet processed
let shipoutOrderId = null;

// ===== Video Recording State =====
let isRecording = false;
let recordingOrderId = null;
let recordingItemId = null;

// ===== Upload State =====
let uploadQueue = [];
let isUploading = false;

// ===== Color Image Cache =====
const colorImageCache = new Map(); // Cache validated color image URLs

/**
 * Try to find a working color image URL from color_images array or color_image
 * @param {Object} product - Product object with color_image and color_images
 * @returns {Promise<string>} - Working image URL or empty string
 */
async function getValidColorImage(product) {
    if (!product) return '';
    
    // Build list of URLs to try
    const urlsToTry = [];
    
    // Add color_images array first (usually has multiple options)
    if (product.color_images && Array.isArray(product.color_images)) {
        urlsToTry.push(...product.color_images);
    }
    
    // Add single color_image as fallback
    if (product.color_image) {
        urlsToTry.push(product.color_image);
    }
    
    if (urlsToTry.length === 0) return '';
    
    // Check cache first
    const cacheKey = urlsToTry.join('|');
    if (colorImageCache.has(cacheKey)) {
        return colorImageCache.get(cacheKey);
    }
    
    // Try each URL
    for (const url of urlsToTry) {
        if (!url) continue;
        
        try {
            const isValid = await checkImageExists(url);
            if (isValid) {
                colorImageCache.set(cacheKey, url);
                console.log('Valid color image found:', url);
                return url;
            }
        } catch (e) {
            // Continue to next URL
        }
    }
    
    // No valid image found
    colorImageCache.set(cacheKey, '');
    return '';
}

/**
 * Check if an image URL exists and is loadable
 * @param {string} url - Image URL to check
 * @returns {Promise<boolean>}
 */
function checkImageExists(url) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = url;
        
        // Timeout after 5 seconds
        setTimeout(() => resolve(false), 5000);
    });
}

/**
 * Load color image into an element, trying multiple URLs
 * @param {HTMLElement} imgElement - Image element to update
 * @param {Object} product - Product object
 * @param {string} fallbackText - Text to show if no image
 */
async function loadColorImage(imgElement, product, fallbackText = 'No preview') {
    if (!imgElement || !product) return;
    
    const validUrl = await getValidColorImage(product);
    
    if (validUrl) {
        imgElement.src = validUrl;
        imgElement.style.display = '';
    } else {
        // Hide image and show placeholder
        imgElement.style.display = 'none';
        const placeholder = imgElement.parentElement?.querySelector('.color-image-placeholder');
        if (placeholder) {
            placeholder.style.display = 'flex';
        }
    }
}

// ===== Eel Exposed Functions (called from Python) =====
eel.expose(onLoginSuccess);
function onLoginSuccess(userData) {
    isLoggedIn = true;
    currentUser = userData;
    userRole = userData.role || 'User';
    
    document.getElementById('login-view').classList.add('hidden');
    document.getElementById('main-view').classList.remove('hidden');
    document.getElementById('user-name').textContent = `${userData.name || userData.email} (${userRole})`;
    document.getElementById('settings-user-name').textContent = userData.name || 'User';
    document.getElementById('settings-user-email').textContent = userData.email;
    
    // Update UI based on role
    updateUIForRole(userRole);
    
    showToast(`Đăng nhập thành công! Role: ${userRole}`, 'success');
}

eel.expose(onLoginError);
function onLoginError(message) {
    document.getElementById('login-error').textContent = message;
    document.getElementById('login-error').classList.remove('hidden');
}

eel.expose(onTokenExpired);
function onTokenExpired() {
    isLoggedIn = false;
    document.getElementById('login-view').classList.remove('hidden');
    document.getElementById('main-view').classList.add('hidden');
    document.getElementById('login-error').textContent = 'Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.';
    document.getElementById('login-error').classList.remove('hidden');
}

eel.expose(onOrderLoaded);
function onOrderLoaded(order) {
    currentOrder = order;
    displayOrder(order);
    // Enable status buttons
    document.querySelectorAll('.status-btn').forEach(btn => btn.disabled = false);
    showToast(`Đã tải đơn hàng #${order.id}`, 'success');
}

eel.expose(onOrderError);
function onOrderError(message) {
    showToast(message, 'error');
    clearOrderDisplay();
}

eel.expose(onScannerData);
function onScannerData(data) {
    // Auto search when scanner sends data
    document.getElementById('order-search').value = data.trim();
    searchOrder();
}

eel.expose(onComPortsLoaded);
function onComPortsLoaded(ports) {
    const select = document.getElementById('com-port-select');
    select.innerHTML = '';
    if (ports.length === 0) {
        select.innerHTML = '<option>Không tìm thấy</option>';
    } else {
        ports.forEach(port => {
            const option = document.createElement('option');
            option.value = port;
            option.textContent = port;
            select.appendChild(option);
        });
    }
}

eel.expose(onScannerStatusChanged);
function onScannerStatusChanged(isConnected, portName) {
    const indicator = document.getElementById('scanner-status-indicator');
    const text = document.getElementById('scanner-status-text');
    const toggle = document.getElementById('scanner-toggle');
    if (isConnected) {
        indicator.textContent = '🟢';
        text.textContent = `Đã kết nối ${portName}`;
        toggle.checked = true;
    } else {
        indicator.textContent = '⚫';
        text.textContent = 'Chưa kết nối';
        toggle.checked = false;
    }
    updateScannerList();
    
    // Update footer status
    updateFooterDeviceStatus('scanner', isConnected, portName);
}

eel.expose(onCameraStatusChanged);
function onCameraStatusChanged(isActive) {
    const toggle = document.getElementById('camera-toggle');
    const dotEl = document.getElementById('camera-status-dot');
    const statusIndicator = document.getElementById('camera-status-indicator');
    const statusText = document.getElementById('camera-status-text');
    
    toggle.checked = isActive;
    dotEl.textContent = isActive ? '🟢' : '⚫';
    statusIndicator.textContent = isActive ? '🟢' : '⚫';
    statusText.textContent = isActive ? 'Đang hoạt động' : 'Chưa kết nối';
    
    // Update footer status
    updateFooterDeviceStatus('camera', isActive);
}

eel.expose(onCameraError);
function onCameraError(errorMessage) {
    showToast(`❌ Camera: ${errorMessage}`, 'error');
}

eel.expose(onCamerasLoaded);
function onCamerasLoaded(cameras) {
    const select = document.getElementById('camera-select');
    select.innerHTML = '';
    
    if (cameras.length === 0) {
        select.innerHTML = '<option value="0">Không tìm thấy camera</option>';
        return;
    }
    
    cameras.forEach((cam, index) => {
        const option = document.createElement('option');
        option.value = cam.index;
        // Only show name if it's different and meaningful
        option.textContent = cam.name || `Camera ${cam.index}`;
        option.selected = cam.index === selectedCameraIndex;
        select.appendChild(option);
    });
}

eel.expose(onCameraFrame);
function onCameraFrame(frameBase64) {
    const preview = document.getElementById('camera-preview');
    if (frameBase64) {
        preview.innerHTML = `<img src="data:image/jpeg;base64,${frameBase64}" class="w-full h-full object-cover rounded-lg">`;
    }
}

eel.expose(onRecordingStatus);
function onRecordingStatus(isRecording, duration) {
    const statusEl = document.getElementById('recording-status');
    const durationEl = document.getElementById('recording-duration');
    const dotEl = document.getElementById('camera-status-dot');
    
    if (isRecording) {
        statusEl.classList.remove('hidden');
        durationEl.classList.remove('hidden');
        durationEl.textContent = formatDuration(duration);
        dotEl.textContent = '🔴';
        dotEl.classList.add('pulse-red');
    } else {
        statusEl.classList.add('hidden');
        durationEl.classList.add('hidden');
        dotEl.textContent = '🟢';
        dotEl.classList.remove('pulse-red');
    }
}

eel.expose(onRecordingLimitReached);
function onRecordingLimitReached(limitSeconds) {
    showToast(`⏱️ Đã đạt giới hạn ghi hình: ${formatDuration(limitSeconds)} - Recording đã dừng`, 'warning');
}

eel.expose(onPackingRecordingComplete);
function onPackingRecordingComplete(orderId, limitSeconds) {
    showToast(`📦 Ghi hình Packing hoàn thành (${formatDuration(limitSeconds)}) - Order #${orderId}`, 'info');
}

eel.expose(onLabelPrinted);
function onLabelPrinted(labelUrl, printerName) {
    showToast(`🖨️ Label đã in thành công tại ${printerName}`, 'success');
}

eel.expose(onVideoUploaded);
function onVideoUploaded(orderId, itemId, videoUrl, remainingInQueue = 0) {
    console.log(`Video uploaded for order ${orderId}, item ${itemId}: ${videoUrl}`);
    
    // Hide progress bar
    hideUploadProgress();
    
    // Update upload status
    isUploading = remainingInQueue > 0;
    updateUploadStatusUI(remainingInQueue);
    
    // Show success notification
    if (remainingInQueue > 0) {
        showToast(`✅ Video đã upload! Còn ${remainingInQueue} video đang chờ...`, 'success');
    } else {
        showToast(`✅ Tất cả video đã upload thành công!`, 'success');
    }
}

eel.expose(onUploadQueued);
function onUploadQueued(orderId, itemId, queueSize) {
    console.log(`Video queued for upload. Queue size: ${queueSize}`);
    isUploading = true;
    updateUploadStatusUI(queueSize);
    showToast(`📤 Video đã thêm vào hàng đợi (${queueSize} video)`, 'info');
}

eel.expose(onUploadStart);
function onUploadStart(orderId, itemId, fileSize) {
    console.log(`Upload started for order ${orderId}, item ${itemId}. Size: ${fileSize}`);
    showUploadProgress(orderId, itemId, fileSize);
}

eel.expose(onUploadError);
function onUploadError(orderId, itemId, errorMessage) {
    console.error(`Upload error for order ${orderId}, item ${itemId}: ${errorMessage}`);
    hideUploadProgress();
    showToast(`❌ Upload thất bại: ${errorMessage}`, 'error');
}

function updateUploadStatusUI(queueSize) {
    // Update or create upload status indicator
    let indicator = document.getElementById('upload-status-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'upload-status-indicator';
        document.body.appendChild(indicator);
    }
    
    if (queueSize > 0 || isUploading) {
        indicator.innerHTML = `
            <div class="upload-status-content">
                <span class="upload-spinner"></span>
                <span>Đang upload ${queueSize > 0 ? `(${queueSize} video)` : '...'}</span>
            </div>
        `;
        indicator.classList.add('visible');
    } else {
        indicator.classList.remove('visible');
    }
}

function showUploadProgress(orderId, itemId, fileSize) {
    let progressBar = document.getElementById('upload-progress-bar');
    if (!progressBar) {
        progressBar = document.createElement('div');
        progressBar.id = 'upload-progress-bar';
        progressBar.innerHTML = `
            <div class="progress-info">
                <span class="progress-text">Uploading video...</span>
                <span class="progress-size">${formatFileSize(fileSize)}</span>
            </div>
            <div class="progress-track">
                <div class="progress-fill"></div>
            </div>
        `;
        document.body.appendChild(progressBar);
    }
    progressBar.classList.add('visible');
    
    // Animate indeterminate progress
    const fill = progressBar.querySelector('.progress-fill');
    fill.style.animation = 'indeterminate 1.5s infinite linear';
}

function hideUploadProgress() {
    const progressBar = document.getElementById('upload-progress-bar');
    if (progressBar) {
        progressBar.classList.remove('visible');
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

eel.expose(onStatusChanged);
function onStatusChanged(orderId, newStatus, success) {
    if (success) {
        showToast(`Đã cập nhật trạng thái: ${newStatus}`, 'success');
        if (currentOrder && currentOrder.id === orderId) {
            currentOrder.fulfill_status = newStatus;
            updateOrderStatusDropdown(newStatus);
        }
    } else {
        showToast('Không thể cập nhật trạng thái', 'error');
    }
}

// ===== Event Listeners =====
document.addEventListener('DOMContentLoaded', () => {
    // Login form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        document.getElementById('login-error').classList.add('hidden');
        await eel.login(email, password)();
    });

    // Search
    document.getElementById('search-btn').addEventListener('click', searchOrder);
    document.getElementById('order-search').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchOrder();
    });

    // Settings
    document.getElementById('settings-btn').addEventListener('click', openSettings);

    // Scanner toggle
    document.getElementById('scanner-toggle').addEventListener('change', async (e) => {
        const port = document.getElementById('com-port-select').value;
        await eel.toggleScanner(e.target.checked, port)();
    });

    // COM port change
    document.getElementById('com-port-select').addEventListener('change', async (e) => {
        const isEnabled = document.getElementById('scanner-toggle').checked;
        if (isEnabled) {
            await eel.toggleScanner(true, e.target.value)();
        }
    });

    // Camera select change
    document.getElementById('camera-select').addEventListener('change', async (e) => {
        selectedCameraIndex = parseInt(e.target.value);
        await eel.selectCamera(selectedCameraIndex)();
    });

    // Camera toggle (in settings panel)
    document.getElementById('camera-toggle').addEventListener('change', async (e) => {
        cameraEnabled = e.target.checked;
        await eel.toggleCamera(cameraEnabled)();
    });

    // Auto record toggle
    document.getElementById('auto-record-toggle').addEventListener('change', async (e) => {
        autoRecordEnabled = e.target.checked;
        await eel.setAutoRecord(autoRecordEnabled)();
    });

    // Disable status buttons initially
    document.querySelectorAll('.status-btn').forEach(btn => btn.disabled = true);

    // Check if already logged in (also triggers auto_start_devices on success)
    eel.checkAuth()();

    // Sync device state after page load/refresh  
    setTimeout(() => {
        try {
            // Don't await - just call and let it sync asynchronously
            eel.syncDeviceState()();
        } catch (e) {
            console.log('syncDeviceState error (ignored):', e);
        }
    }, 500);

    // Load COM ports and cameras
    try {
        eel.getComPorts()();
        eel.getAvailableCameras()();
    } catch (e) {
        console.log('Device init error (ignored):', e);
    }
    
    // Load saved settings
    loadSettings();
    
    // Load printers
    refreshPrinterList();
});

// ===== Settings Functions =====
async function loadSettings() {
    // Load from localStorage and sync with backend
    const savedLimit = localStorage.getItem('recordingLimit');
    if (savedLimit) {
        recordingLimit = parseInt(savedLimit);
        document.getElementById('record-limit').value = recordingLimit;
        // Sync with backend
        await eel.setRecordingLimit(recordingLimit)();
    }
    
    const savedAutoRecord = localStorage.getItem('autoRecord');
    if (savedAutoRecord !== null) {
        autoRecordEnabled = savedAutoRecord === 'true';
        document.getElementById('auto-record-toggle').checked = autoRecordEnabled;
        // Sync with backend
        await eel.setAutoRecord(autoRecordEnabled)();
    }
    
    const savedCamera = localStorage.getItem('selectedCamera');
    if (savedCamera !== null) {
        selectedCameraIndex = parseInt(savedCamera);
    }
    
    // Load saved printer
    const savedPrinter = localStorage.getItem('selectedPrinter');
    if (savedPrinter) {
        selectedPrinter = savedPrinter;
    }
}

async function updateRecordLimit() {
    const input = document.getElementById('record-limit');
    let value = parseInt(input.value);
    
    // Validate range (min 10s, max 3600s)
    if (value < 10) value = 10;
    if (value > 3600) value = 3600;
    input.value = value;
    
    recordingLimit = value;
    localStorage.setItem('recordingLimit', value);
    await eel.setRecordingLimit(value)();
    showToast(`Giới hạn ghi hình: ${value}s`, 'success');
}

async function refreshCameraList() {
    showToast('Đang tìm camera...', 'info');
    await eel.getAvailableCameras()();
}

// ===== Printer Functions =====
async function refreshPrinterList() {
    const select = document.getElementById('printer-select-settings');
    const statusIndicator = document.getElementById('printer-status-indicator');
    const statusText = document.getElementById('printer-status-text');
    
    if (!select) return;
    
    select.innerHTML = '<option>Đang tìm...</option>';
    if (statusIndicator) statusIndicator.textContent = '🔄';
    if (statusText) statusText.textContent = 'Đang tìm máy in...';
    
    try {
        const result = await eel.getConnectedPrinters()();
        
        if (result && result.success && result.printers && result.printers.length > 0) {
            const printers = result.printers;
            const readyPrinters = printers.filter(p => p.status === 'Ready');
            
            select.innerHTML = `
                <option value="">-- Chọn --</option>
                ${printers.map(p => `
                    <option value="${p.name}" ${p.status !== 'Ready' ? 'disabled' : ''} ${selectedPrinter === p.name ? 'selected' : ''}>
                        ${p.name} ${p.status === 'Ready' ? '✓' : '⚠️'}
                    </option>
                `).join('')}
            `;
            
            if (statusIndicator) statusIndicator.textContent = readyPrinters.length > 0 ? '🟢' : '🟡';
            if (statusText) statusText.textContent = `${readyPrinters.length}/${printers.length} máy in sẵn sàng`;
            
            // Auto-select if only one ready printer and no saved selection
            if (!selectedPrinter && readyPrinters.length === 1) {
                selectedPrinter = readyPrinters[0].name;
                select.value = selectedPrinter;
                localStorage.setItem('selectedPrinter', selectedPrinter);
            }
            
            // Restore saved selection
            if (selectedPrinter) {
                select.value = selectedPrinter;
            }
            
            // Update footer status
            updateFooterDeviceStatus('printer', readyPrinters.length > 0, selectedPrinter);
        } else {
            select.innerHTML = '<option value="">Không tìm thấy</option>';
            if (statusIndicator) statusIndicator.textContent = '🔴';
            if (statusText) statusText.textContent = 'Không có máy in';
            updateFooterDeviceStatus('printer', false);
        }
    } catch (e) {
        console.error('Error getting printers:', e);
        select.innerHTML = '<option value="">Lỗi</option>';
        if (statusIndicator) statusIndicator.textContent = '🔴';
        if (statusText) statusText.textContent = 'Lỗi nhận diện';
        updateFooterDeviceStatus('printer', false);
    }
    
    // Add change event listener
    select.onchange = function() {
        selectedPrinter = this.value;
        localStorage.setItem('selectedPrinter', selectedPrinter);
        if (selectedPrinter) {
            showToast(`🖨️ Đã chọn máy in: ${selectedPrinter}`, 'success');
            updateFooterDeviceStatus('printer', true, selectedPrinter);
        }
    };
}

// Update footer device status indicators
function updateFooterDeviceStatus(device, isConnected, name = '') {
    const indicator = document.getElementById(`${device}-indicator`);
    const label = document.getElementById(`${device}-label`);
    
    if (!indicator || !label) return;
    
    if (device === 'scanner') {
        indicator.textContent = isConnected ? '📷' : '📷';
        indicator.style.opacity = isConnected ? '1' : '0.4';
        label.textContent = isConnected ? `Scanner: ${name}` : 'Scanner: --';
        label.className = isConnected ? 'text-sm text-green-400' : 'text-sm text-gray-500';
    } else if (device === 'camera') {
        indicator.textContent = '🎥';
        indicator.style.opacity = isConnected ? '1' : '0.4';
        label.textContent = isConnected ? 'Camera: OK' : 'Camera: --';
        label.className = isConnected ? 'text-sm text-green-400' : 'text-sm text-gray-500';
    } else if (device === 'printer') {
        indicator.textContent = '🖨️';
        indicator.style.opacity = isConnected ? '1' : '0.4';
        label.textContent = isConnected && name ? `Printer: ${name}` : 'Printer: --';
        label.className = isConnected ? 'text-sm text-green-400' : 'text-sm text-gray-500';
    }
}

// Test print sample label
async function testPrintLabel() {
    const printerName = selectedPrinter || localStorage.getItem('selectedPrinter');
    
    if (!printerName) {
        showToast('Vui lòng chọn máy in trước!', 'warning');
        return;
    }
    
    const testLabelUrl = 'https://s3.us-east-005.backblazeb2.com/Lemiex-Fulfillment/converted_label/label_22.jpg?random=739207';
    
    showToast('🖨️ Đang in label test...', 'info');
    
    try {
        const result = await eel.printLabel(testLabelUrl, printerName)();
        
        if (result && result.success) {
            showToast('✅ In label thành công!', 'success');
        } else {
            showToast('❌ Lỗi in: ' + (result?.message || 'Không xác định'), 'error');
        }
    } catch (e) {
        console.error('Test print error:', e);
        showToast('❌ Lỗi: ' + e.message, 'error');
    }
}

// ===== Functions =====
async function searchOrder() {
    const orderId = document.getElementById('order-search').value.trim();
    if (!orderId) {
        showToast('Vui lòng nhập Order ID', 'warning');
        return;
    }
    showLoading();
    await eel.searchOrder(orderId)();
}

function displayOrder(order) {
    // Note display at top (if exists)
    const noteSection = document.getElementById('order-note-section');
    if (noteSection) {
        if (order.note) {
            noteSection.innerHTML = `
                <div class="bg-yellow-900/50 border border-yellow-600 rounded-lg p-3 mb-4">
                    <div class="flex items-center gap-2">
                        <span class="text-yellow-400 font-bold">📝 Note:</span>
                        <span class="text-yellow-200">${order.note}</span>
                    </div>
                </div>
            `;
            noteSection.classList.remove('hidden');
        } else {
            noteSection.classList.add('hidden');
        }
    }
    
    // Header with seller
    document.getElementById('order-id-display').textContent = `#${order.id}`;
    document.getElementById('ref-id').textContent = `Ref: ${order.ref_id || '-'}`;
    
    // Seller username in header
    const sellerEl = document.getElementById('seller-username');
    if (sellerEl && order.seller) {
        sellerEl.textContent = `👤 ${order.seller.username || order.seller.name || '-'}`;
    }
    
    // Tracking ID
    const trackingEl = document.getElementById('tracking-id');
    if (trackingEl) {
        trackingEl.textContent = `Tracking: ${order.tracking_id || '-'}`;
    }

    // Order Status Dropdown
    updateOrderStatusDropdown(order.fulfill_status || order.order_stt || 'new_order');
    
    // SINGLE/MULTI indicator - use total_quantity or calculate from items
    const items = order.items || [];
    let totalQuantity = order.total_quantity;
    if (!totalQuantity || totalQuantity < items.length) {
        totalQuantity = items.reduce((sum, item) => sum + (item.quantity || 1), 0);
    }
    const orderType = totalQuantity >= 2 ? 'ĐƠN NHIỀU ÁO' : 'ĐƠN LẺ';
    const orderTypeClass = totalQuantity >= 2 ? 'bg-warning' : 'bg-success';
    
    // Add Timeline and Order Type to header
    const headerDiv = document.querySelector('#order-note-section').parentElement;
    let timelineSection = document.getElementById('order-timeline-section');
    if (!timelineSection) {
        timelineSection = document.createElement('div');
        timelineSection.id = 'order-timeline-section';
        timelineSection.className = 'px-4 pt-2';
        headerDiv.appendChild(timelineSection);
    }
    
    timelineSection.innerHTML = `
        <div class="flex items-center justify-between bg-dark-100 mx-0 px-4 py-3 rounded-lg">
            <div class="flex items-center gap-4">
                <span class="px-3 py-1 ${orderTypeClass} rounded-lg text-white font-bold">${orderType}</span>
                <span class="text-gray-400">${items.length} item(s)</span>
            </div>
            ${createTimelineHTML(order)}
        </div>
    `;

    // Items
    const container = document.getElementById('items-container');
    document.getElementById('items-count').textContent = `(${items.length} items)`;

    if (items.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400 py-8">Không có sản phẩm</div>';
        return;
    }

    container.innerHTML = items.map((item, index) => {
        const product = item.product || {};
        const productName = product.product_name || item.product_name || 'Unknown Product';
        const style = product.style || item.style || '';
        const color = product.color || item.color || '';
        const size = product.size || item.size || '';
        
        return `
        <div class="product-card-new" data-item-index="${index}">
            <!-- Left: Color Image -->
            <div class="flex flex-col gap-3 items-center color-image-container">
                <img class="color-image w-60 h-60 rounded-lg object-cover border-2 border-gray-600" 
                     alt="${color}" 
                     style="display: none;"
                     onerror="this.style.display='none'">
                <div class="color-image-placeholder w-60 h-60 rounded-lg bg-gray-800 flex items-center justify-center border-2 border-gray-600">
                    <div class="loading-spinner-small"></div>
                </div>
            </div>
            
            <!-- Middle: Product Info -->
            <div class="flex-1 flex flex-col gap-3">
                <div class="text-lg font-bold text-white">${productName}</div>
                
                <!-- Product variant info - PROMINENT with styled borders -->
                <div class="flex flex-wrap gap-3">
                    ${style ? `<span class="variant-badge variant-style px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-purple-400 bg-purple-600/80">📦 ${style}</span>` : ''}
                    ${color ? `<span class="variant-badge variant-color px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-blue-400 bg-blue-600/80">🎨 ${color}</span>` : ''}
                    ${size ? `<span class="variant-badge variant-size px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-green-400 bg-green-600/80">📏 ${size}</span>` : ''}
                </div>
                
                <div class="flex gap-4 text-sm text-gray-400">
                    <span>Số lượng: <strong class="text-white">${item.quantity || 1}</strong></span>
                </div>
                
                <!-- Item Timeline -->
                <div class="mt-2">
                    ${createItemTimelineSmall(item)}
                </div>
            </div>
            
            <!-- Middle: Mockup Image -->
            <div class="flex flex-col gap-3">
                <img src="${item.mockup || 'https://via.placeholder.com/120'}" 
                     alt="${productName}" class="w-60 h-60 rounded-lg object-cover bg-gray-900"
                     onerror="this.src='https://via.placeholder.com/120?text=No+Image'">
            </div>
            
            <!-- Right: Design Previews -->
            <div class="flex flex-col gap-2">
                ${item.designs && item.designs.length > 0 ? `
                    <div class="text-sm text-gray-400 font-semibold mb-1">Designs:</div>
                    <div class="flex gap-3">
                        ${item.designs.map((d, idx) => `
                            <div class="design-preview-card bg-gray-800 rounded-lg p-2 border border-gray-700" data-json-url="${d.json_url}" data-item-id="${item.id}" data-design-idx="${idx}">
                                <div class="text-xs text-center text-gray-400 mb-1 capitalize font-semibold">${d.position}</div>
                                <div class="design-preview-image w-28 h-28 bg-gray-900 rounded flex items-center justify-center">
                                    <div class="loading-spinner-small"></div>
                                </div>
                                <div class="text-xs text-gray-500 mt-1 text-center">
                                    ${d.stitch_count ? `${(d.stitch_count/1000).toFixed(1)}k st` : ''}
                                </div>
                                <div class="text-xs text-gray-500 text-center">
                                    ${d.width_mm ? `${d.width_mm.toFixed(0)}×${d.height_mm?.toFixed(0) || 0}mm` : ''}
                                </div>
                                ${d.color_count ? `<div class="text-xs text-gray-500 text-center">${d.color_count} colors</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<div class="text-gray-500 text-sm">No designs</div>'}
            </div>
        </div>
    `}).join('');
    
    // Load color images async for each item
    loadColorImagesForItems(items);
    
    // Load design previews from json_url
    loadDesignPreviews();
}

/**
 * Load color images for all items in the list
 * Tries multiple URLs from color_images array until one works
 */
async function loadColorImagesForItems(items) {
    const cards = document.querySelectorAll('.product-card-new[data-item-index]');
    
    for (const card of cards) {
        const index = parseInt(card.dataset.itemIndex);
        const item = items[index];
        if (!item) continue;
        
        const product = item.product || item;
        const imgElement = card.querySelector('.color-image');
        const placeholder = card.querySelector('.color-image-placeholder');
        
        if (!imgElement) continue;
        
        try {
            const validUrl = await getValidColorImage(product);
            
            if (validUrl) {
                imgElement.src = validUrl;
                imgElement.style.display = '';
                if (placeholder) placeholder.style.display = 'none';
            } else {
                imgElement.style.display = 'none';
                if (placeholder) {
                    placeholder.innerHTML = '<span class="text-gray-500">No preview</span>';
                }
            }
        } catch (e) {
            imgElement.style.display = 'none';
            if (placeholder) {
                placeholder.innerHTML = '<span class="text-gray-500">No preview</span>';
            }
        }
    }
}

async function loadDesignPreviews() {
    const previewCards = document.querySelectorAll('.design-preview-card[data-json-url]');
    
    for (const card of previewCards) {
        const jsonUrl = card.dataset.jsonUrl;
        const imageContainer = card.querySelector('.design-preview-image');
        
        // Skip if no valid URL
        if (!jsonUrl || jsonUrl === 'null' || jsonUrl === 'undefined' || jsonUrl === '') {
            imageContainer.innerHTML = `<span class="text-gray-600 text-xs">No file</span>`;
            continue;
        }
        
        try {
            const result = await eel.fetchDesignPreview(jsonUrl)();
            if (result && result.success && result.image_data) {
                imageContainer.innerHTML = `<img src="data:image/${result.format || 'png'};base64,${result.image_data}" class="w-full h-full object-contain rounded">`;
            } else {
                imageContainer.innerHTML = `<span class="text-gray-600 text-xs">No preview</span>`;
            }
        } catch (e) {
            imageContainer.innerHTML = `<span class="text-red-500 text-xs">Error</span>`;
        }
    }
}

// Normalize status from API format (e.g., "FulfillStatus.CANCELLED" -> "cancelled")
function normalizeStatus(status) {
    if (!status) return 'new_order';
    
    // If it's already in simple format, just lowercase it
    let normalized = status.toLowerCase();
    
    // Handle FulfillStatus.XXX format
    if (normalized.includes('fulfillstatus.')) {
        normalized = normalized.replace('fulfillstatus.', '');
    }
    
    // Map API status names to our status names
    const statusMap = {
        'new': 'new_order',
        'in_process': 'producing',
        'fulfilled': 'delivered',
        'on_hold': 'return_to_support'
    };
    
    return statusMap[normalized] || normalized;
}

function updateOrderStatusDropdown(status) {
    const select = document.getElementById('order-status-select');
    // Normalize status first
    const normalizedStatus = normalizeStatus(status);
    
    // Valid statuses for the dropdown
    const validStatuses = ['new_order', 'producing', 'shipped', 'return_to_support', 'cancelled', 'delivered'];
    
    if (validStatuses.includes(normalizedStatus)) {
        select.value = normalizedStatus;
    } else {
        select.value = '';
    }
    
    // Update dropdown color based on status
    select.className = `rounded-lg px-4 py-2 text-sm font-bold focus:outline-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed status-${normalizedStatus}`;
    
    // Enable dropdown when order is loaded
    select.disabled = !currentOrder;
}

function clearOrderDisplay() {
    document.getElementById('order-id-display').textContent = '# ---';
    document.getElementById('ref-id').textContent = 'Ref: -';
    document.getElementById('seller-username').textContent = '';
    document.getElementById('tracking-id').textContent = 'Tracking: -';
    const statusSelect = document.getElementById('order-status-select');
    statusSelect.value = '';
    statusSelect.className = 'rounded-lg px-4 py-2 text-sm font-bold focus:outline-none cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed bg-gray-600';
    statusSelect.disabled = true;
    document.getElementById('items-container').innerHTML = '<div class="text-center text-gray-400 py-8">Chưa có đơn hàng nào được chọn</div>';
    document.getElementById('items-count').textContent = '(0 items)';
    currentOrder = null;
}

function showLoading() {
    document.getElementById('items-container').innerHTML = `
        <div class="flex flex-col items-center justify-center py-12">
            <div class="loading-spinner"></div>
            <p class="mt-4 text-gray-400">Đang tải...</p>
        </div>
    `;
}

// ===== Settings =====
function openSettings(section = null) {
    document.getElementById('settings-overlay').classList.remove('hidden');
    document.getElementById('settings-panel').style.transform = 'translateX(0)';
    
    // Scroll to specific section if provided
    if (section === 'camera') {
        setTimeout(() => {
            const cameraSection = document.getElementById('settings-camera-section');
            if (cameraSection) {
                cameraSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 100);
    }
}

function closeSettings() {
    document.getElementById('settings-overlay').classList.add('hidden');
    document.getElementById('settings-panel').style.transform = 'translateX(100%)';
}

async function logout() {
    await eel.logout()();
    isLoggedIn = false;
    closeSettings();
    document.getElementById('main-view').classList.add('hidden');
    document.getElementById('login-view').classList.remove('hidden');
    clearOrderDisplay();
    showToast('Đã đăng xuất', 'info');
}

// ===== Order Status Change =====
async function changeOrderStatus(newStatus) {
    if (!currentOrder) {
        showToast('Chưa có đơn hàng', 'warning');
        return;
    }
    if (!newStatus) {
        return;
    }
    
    const select = document.getElementById('order-status-select');
    const previousStatus = currentOrder.fulfill_status;
    select.disabled = true;
    
    try {
        const result = await eel.changeFulfillStatus(currentOrder.id, newStatus)();
        if (result && result.success) {
            currentOrder.fulfill_status = newStatus;
            updateOrderStatusDropdown(newStatus);
            showToast(`Đã cập nhật trạng thái: ${newStatus}`, 'success');
        } else {
            showToast(result?.message || 'Lỗi cập nhật trạng thái', 'error');
            // Reset dropdown to previous value
            updateOrderStatusDropdown(previousStatus);
        }
    } catch (e) {
        showToast('Lỗi kết nối', 'error');
        updateOrderStatusDropdown(previousStatus);
    } finally {
        select.disabled = false;
    }
}

// ===== Refresh Functions =====
async function refreshScanner() {
    showToast('Đang refresh scanner...', 'info');
    const result = await eel.refreshScanner()();
    if (result.success) {
        showToast(`Scanner kết nối thành công trên ${result.port}`, 'success');
        // Update toggle state
        document.getElementById('scanner-toggle').checked = true;
    } else {
        showToast(result.message || 'Không tìm thấy scanner', 'warning');
    }
    // Reload COM ports
    await eel.getComPorts()();
}

async function refreshCamera() {
    showToast('Đang refresh camera...', 'info');
    const result = await eel.refreshCamera()();
    if (result.success) {
        showToast('Camera đã được refresh', 'success');
        document.getElementById('camera-toggle').checked = true;
    } else {
        showToast(result.message || 'Lỗi refresh camera', 'error');
    }
}

// ===== Scanner List =====
function updateScannerList() {
    // This would be populated by Python with active scanners
}

// ===== Role-based UI =====
function updateUIForRole(role) {
    // Show/hide elements based on role
    const roleUpper = (role || '').toUpperCase();
    
    // Update header title with role
    const headerTitle = document.querySelector('header h1');
    if (headerTitle) {
        headerTitle.textContent = `LEMIEX - ${roleUpper}`;
    }
    
    // For QC role, hide status dropdown (they use scan to activate)
    const statusSelect = document.getElementById('order-status-select');
    if (statusSelect) {
        if (roleUpper === 'QC' || roleUpper === 'PACKING' || roleUpper === 'SHIPOUT') {
            statusSelect.style.display = 'none';
        } else {
            statusSelect.style.display = 'block';
        }
    }
}

// ===== Timeline Component =====
function createTimelineHTML(order) {
    // Extract status from order
    const staffActive = order.status === 1 || order.status === '1';
    const qcActive = order.qc_status === 1 || order.qc_status === '1';
    const packActive = order.packing_status === 1 || order.packing_status === '1';
    const shipActive = order.shipout_status === 1 || order.shipout_status === '1';
    
    return `
        <div class="flex items-center gap-2 text-sm">
            <div class="flex items-center gap-1">
                <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${staffActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${staffActive ? '✓' : '1'}
                </span>
                <span class="${staffActive ? 'text-success font-bold' : 'text-gray-500'}">STAFF</span>
            </div>
            <div class="w-4 h-0.5 ${qcActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex items-center gap-1">
                <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${qcActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${qcActive ? '✓' : '2'}
                </span>
                <span class="${qcActive ? 'text-success font-bold' : 'text-gray-500'}">QC</span>
            </div>
            <div class="w-4 h-0.5 ${packActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex items-center gap-1">
                <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${packActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${packActive ? '✓' : '3'}
                </span>
                <span class="${packActive ? 'text-success font-bold' : 'text-gray-500'}">PACK</span>
            </div>
            <div class="w-4 h-0.5 ${shipActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex items-center gap-1">
                <span class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${shipActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${shipActive ? '✓' : '4'}
                </span>
                <span class="${shipActive ? 'text-success font-bold' : 'text-gray-500'}">SHIP</span>
            </div>
        </div>
    `;
}

function createItemTimelineHTML(item) {
    // Item-level timeline - aggregate from designs
    const designs = item.designs || [];
    
    // STAFF: item.status is boolean (true/false) OR designs[].status is number (1/0)
    const staffActive = item.status === true || designs.some(d => d.status === 1);
    
    // QC/Pack/Ship: only in designs[] as number (1/0)
    const qcActive = designs.some(d => d.qc_status === 1);
    const packActive = designs.some(d => d.packing_status === 1);
    const shipActive = designs.some(d => d.shipout_status === 1);
    
    console.log('Timeline status:', { 
        itemId: item.id,
        itemStatus: item.status, 
        staffActive, 
        qcActive, 
        packActive, 
        shipActive,
        designs: designs.map(d => ({ pos: d.position, status: d.status, qc: d.qc_status, pack: d.packing_status, ship: d.shipout_status }))
    });
    
    return `
        <div class="flex items-center gap-3 text-base">
            <div class="flex flex-col items-center">
                <span class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${staffActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${staffActive ? '✓' : '1'}
                </span>
                <span class="${staffActive ? 'text-success font-bold' : 'text-gray-500'} mt-1">STAFF</span>
            </div>
            <div class="w-8 h-1 ${qcActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex flex-col items-center">
                <span class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${qcActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${qcActive ? '✓' : '2'}
                </span>
                <span class="${qcActive ? 'text-success font-bold' : 'text-gray-500'} mt-1">QC</span>
            </div>
            <div class="w-8 h-1 ${packActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex flex-col items-center">
                <span class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${packActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${packActive ? '✓' : '3'}
                </span>
                <span class="${packActive ? 'text-success font-bold' : 'text-gray-500'} mt-1">PACK</span>
            </div>
            <div class="w-8 h-1 ${shipActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <div class="flex flex-col items-center">
                <span class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold ${shipActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                    ${shipActive ? '✓' : '4'}
                </span>
                <span class="${shipActive ? 'text-success font-bold' : 'text-gray-500'} mt-1">SHIP</span>
            </div>
        </div>
    `;
}

// Update popup timeline in realtime (without recreating popup)
function updatePopupTimeline(freshItem) {
    const timelineContainer = document.getElementById('qc-popup-timeline');
    if (!timelineContainer) return false;
    
    // Check if this is the same item
    const currentItemId = timelineContainer.dataset.itemId;
    if (String(currentItemId) !== String(freshItem.id)) return false;
    
    console.log('Updating popup timeline realtime for item:', freshItem.id);
    
    // Update timeline HTML with animation
    const newTimelineHTML = createItemTimelineHTML(freshItem);
    timelineContainer.innerHTML = newTimelineHTML;
    
    // Add flash animation to highlight the update
    timelineContainer.classList.add('timeline-updated');
    setTimeout(() => {
        timelineContainer.classList.remove('timeline-updated');
    }, 1500);
    
    // Update data attribute
    timelineContainer.dataset.itemId = freshItem.id;
    
    return true;
}

// Show notification when MULTI order is fully QC completed
function showMultiOrderCompleteNotification(order, itemCount) {
    console.log('🎉 MULTI order fully QC completed:', order.id, itemCount, 'items');
    
    // Remove any existing notification
    const existing = document.getElementById('multi-complete-notification');
    if (existing) existing.remove();
    
    const notificationHTML = `
        <div id="multi-complete-notification" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 animate-fade-in">
            <div class="bg-gradient-to-br from-green-600 to-green-800 rounded-3xl p-8 max-w-lg mx-4 text-center shadow-2xl border-4 border-green-400 animate-bounce-in">
                <div class="text-8xl mb-4">🎉</div>
                <h2 class="text-4xl font-bold text-white mb-4">HOÀN THÀNH!</h2>
                <p class="text-2xl text-green-100 mb-2">ĐƠN NHIỀU ÁO #${order.id}</p>
                <p class="text-3xl font-bold text-yellow-300 mb-6">${itemCount} ITEMS ĐÃ QC XONG</p>
                <div class="flex gap-4 justify-center">
                    <button onclick="closeMultiCompleteNotification()" class="px-8 py-4 bg-white text-green-700 rounded-xl font-bold text-xl hover:bg-gray-100 transition">
                        ✓ Đã hiểu
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', notificationHTML);
    
    // Play success sound if available
    try {
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleREXlKTRw29KJB6CrNPIhV4hGmiqz8V8VR8nY5rNuHxXHjhZh7+wdWAoQ1Vxr6dpVThDUmGhjmpYPEZbX4+AYVlDS1VdgXdfU0tTV16BfF9WUVRXXH51VlJUV1hecnBbVldZXF5qbV1ZWltdX2ZoX1tbXV9fY2RhXl1eX2BhYWBfXl9gYGFhYF9fYGBgYGFgYGBgYGBgYGBgYGBgYGBgYF9gYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBgYGBg');
        audio.volume = 0.5;
        audio.play().catch(() => {});
    } catch (e) {}
    
    // Auto close after 5 seconds
    setTimeout(() => {
        closeMultiCompleteNotification();
    }, 5000);
}

function closeMultiCompleteNotification() {
    const notification = document.getElementById('multi-complete-notification');
    if (notification) {
        notification.style.opacity = '0';
        notification.style.transform = 'scale(0.9)';
        notification.style.transition = 'all 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }
}

// Small timeline for item list display
function createItemTimelineSmall(item) {
    // Aggregate from designs
    const designs = item.designs || [];
    
    // STAFF: item.status is boolean (true/false) OR designs[].status is number (1/0)
    const staffActive = item.status === true || designs.some(d => d.status === 1);
    
    // QC/Pack/Ship: only in designs[] as number (1/0)
    const qcActive = designs.some(d => d.qc_status === 1);
    const packActive = designs.some(d => d.packing_status === 1);
    const shipActive = designs.some(d => d.shipout_status === 1);
    
    return `
        <div class="flex items-center gap-1 text-xs">
            <span class="w-5 h-5 rounded-full flex items-center justify-center font-bold ${staffActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                ${staffActive ? '✓' : '1'}
            </span>
            <div class="w-2 h-0.5 ${qcActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <span class="w-5 h-5 rounded-full flex items-center justify-center font-bold ${qcActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                ${qcActive ? '✓' : '2'}
            </span>
            <div class="w-2 h-0.5 ${packActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <span class="w-5 h-5 rounded-full flex items-center justify-center font-bold ${packActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                ${packActive ? '✓' : '3'}
            </span>
            <div class="w-2 h-0.5 ${shipActive ? 'bg-success' : 'bg-gray-600'}"></div>
            <span class="w-5 h-5 rounded-full flex items-center justify-center font-bold ${shipActive ? 'bg-success text-white' : 'bg-gray-600 text-gray-400'}">
                ${shipActive ? '✓' : '4'}
            </span>
            <span class="ml-2 text-gray-500">STAFF→QC→PACK→SHIP</span>
        </div>
    `;
}

// ===== Video Recording Functions (use Python backend) =====
async function startVideoRecording(orderId, itemId) {
    if (isRecording) {
        console.log('Already recording, skip startVideoRecording');
        return;
    }
    
    try {
        recordingOrderId = orderId;
        recordingItemId = itemId;
        
        const result = await eel.startQCRecording(parseInt(orderId), parseInt(itemId))();
        
        if (result && result.success) {
            isRecording = true;
            console.log(`Recording started for order ${orderId}, item ${itemId}`);
            showToast('🎥 Đang ghi hình...', 'info');
            updateRecordingUI(true);
        } else {
            console.warn('Failed to start recording:', result?.message);
        }
        
    } catch (e) {
        console.error('Failed to start recording:', e);
    }
}

async function stopVideoRecording() {
    if (!isRecording) {
        return;
    }
    
    try {
        isRecording = false;
        updateRecordingUI(false);
        
        const result = await eel.stopQCRecording()();
        console.log('Recording stop result:', result);
        
        if (result && result.success) {
            showToast('📤 Đang upload video...', 'info');
        }
        
        recordingOrderId = null;
        recordingItemId = null;
        
    } catch (e) {
        console.error('Failed to stop recording:', e);
    }
}

function updateRecordingUI(isRecording) {
    // Add/remove recording indicator
    let indicator = document.getElementById('recording-indicator');
    
    if (isRecording) {
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'recording-indicator';
            indicator.className = 'fixed top-4 right-4 bg-error text-white px-4 py-2 rounded-full flex items-center gap-2 z-50 animate-pulse';
            indicator.innerHTML = '<span class="w-3 h-3 bg-white rounded-full"></span> REC';
            document.body.appendChild(indicator);
        }
    } else {
        if (indicator) {
            indicator.remove();
        }
    }
}

// ===== QC Item Popup =====
function showQCItemPopup(item, order) {
    // Use total_quantity from API response for SINGLE/MULTI detection
    const totalQuantity = order.total_quantity || order.items?.length || 1;
    console.log('showQCItemPopup - order.total_quantity:', order.total_quantity, 'calculated totalQuantity:', totalQuantity);
    const orderType = totalQuantity >= 2 ? 'ĐƠN NHIỀU ÁO' : 'ĐƠN LẺ';
    const orderTypeClass = totalQuantity >= 2 ? 'bg-warning' : 'bg-success';
    console.log('Order type:', orderType, 'totalQuantity:', totalQuantity);
    const items = order.items || [];
    
    // Find item index
    const itemIndex = items.findIndex(i => String(i.id) === String(item.id)) + 1;
    
    // Get product info (from track API response format)
    const product = item.product || {};
    const productName = product.product_name || item.product_name || 'Unknown Product';
    const style = product.style || item.style || '';
    const color = product.color || item.color || '';
    const size = product.size || item.size || '';
    const mockup = item.mockup || 'https://via.placeholder.com/300';
    
    // Store product for async color image loading
    const productData = JSON.stringify(product).replace(/"/g, '&quot;');
    
    const popupHTML = `
        <div id="qc-popup" class="fixed inset-0 bg-black/95 z-50 flex items-center justify-center p-4">
            <div class="bg-dark-200 rounded-2xl w-full max-w-7xl max-h-[95vh] overflow-auto">
                <!-- Header -->
                <div class="p-6 border-b border-gray-700 flex items-center justify-between">
                    <div class="flex items-center gap-4">
                        <h2 class="text-3xl font-bold text-primary">Order #${order.id}</h2>
                        <span class="px-5 py-2 ${orderTypeClass} rounded-xl text-white font-bold text-xl animate-pulse">${orderType}</span>
                        <span class="px-4 py-2 bg-gray-700 rounded-lg text-white font-bold">
                            Item ${itemIndex || item.id} / ${totalQuantity}
                        </span>
                    </div>
                    <button onclick="closeQCPopup()" class="text-3xl hover:text-danger">✕</button>
                </div>
                
                <!-- Order Type Banner for MULTI -->
                ${totalQuantity >= 2 ? `
                    <div class="bg-warning/20 border-b border-warning px-6 py-3 text-center">
                        <span class="text-warning font-bold text-lg">⚠️ ĐƠN NHIỀU ÁO - ${totalQuantity} ITEMS - Đang xem item ${itemIndex}</span>
                    </div>
                ` : ''}
                
                <!-- Timeline -->
                <div id="qc-popup-timeline" class="p-4 border-b border-gray-700 flex justify-center" data-item-id="${item.id}">
                    ${createItemTimelineHTML(item)}
                </div>
                
                <!-- Item Content - 3 columns, 2 rows -->
                <div class="p-6">
                    <!-- Row 1: Product Preview | Variant Details | Mockup -->
                    <div class="grid grid-cols-3 gap-6 mb-6">
                        <!-- Column 1: Product Preview -->
                        <div class="flex flex-col items-center" id="popup-color-image-container" data-product="${productData}">
                            <h4 class="text-lg font-bold mb-3 text-gray-400">Product Preview</h4>
                            <img id="popup-color-image" class="w-full max-w-72 h-72 rounded-xl object-cover border-4 border-gray-600" style="display: none;" alt="${color}">
                            <div id="popup-color-placeholder" class="w-full max-w-72 h-72 rounded-xl bg-gray-800 flex items-center justify-center border-4 border-gray-600">
                                <div class="loading-spinner"></div>
                            </div>
                        </div>
                        
                        <!-- Column 2: Variant Details -->
                        <div class="flex flex-col">
                            <h4 class="text-lg font-bold mb-3 text-gray-400">Variant Details</h4>
                            <h3 class="text-2xl font-bold mb-4">${productName}</h3>
                            
                            <!-- Variant Info - BIG with styled borders -->
                            <div class="flex flex-col gap-3">
                                ${style ? `<span class="variant-badge variant-style px-6 py-3 rounded-xl text-white font-bold text-xl text-center border-2 border-purple-400 bg-purple-600/80 shadow-lg shadow-purple-500/30">📦 ${style}</span>` : ''}
                                ${color ? `<span class="variant-badge variant-color px-6 py-3 rounded-xl text-white font-bold text-xl text-center border-2 border-blue-400 bg-blue-600/80 shadow-lg shadow-blue-500/30">🎨 ${color}</span>` : ''}
                                ${size ? `<span class="variant-badge variant-size px-6 py-3 rounded-xl text-white font-bold text-xl text-center border-2 border-green-400 bg-green-600/80 shadow-lg shadow-green-500/30">📏 ${size}</span>` : ''}
                            </div>
                            
                            <div class="text-xl text-gray-400 mt-4">
                                Số lượng: <strong class="text-white text-2xl">${item.quantity || 1}</strong>
                            </div>
                        </div>
                        
                        <!-- Column 3: Mockup -->
                        <div class="flex flex-col items-center">
                            <h4 class="text-lg font-bold mb-3 text-gray-400">Mockup</h4>
                            <img src="${mockup}" alt="${productName}" class="w-full max-w-72 h-72 rounded-xl object-cover bg-gray-900 border-4 border-primary">
                        </div>
                    </div>
                    
                    <!-- Row 2: Designs Preview -->
                    ${item.designs && item.designs.length > 0 ? `
                        <div class="border-t border-gray-700 pt-6">
                            <h4 class="text-lg font-bold mb-4">🎨 Designs (${item.designs.length} positions):</h4>
                            <div class="grid grid-cols-3 gap-4">
                                ${item.designs.map((d, idx) => `
                                    <div class="bg-gray-800 rounded-lg p-4 border border-gray-700 popup-design-card" data-json-url="${d.json_url}" data-design-idx="${idx}">
                                        <div class="flex items-center justify-between mb-2">
                                            <span class="text-lg font-bold capitalize text-primary">${d.position}</span>
                                            <span class="text-sm text-gray-400">${d.stitch_count ? `${(d.stitch_count/1000).toFixed(1)}k stitches` : ''}</span>
                                        </div>
                                        
                                        <!-- Design Preview Image -->
                                        <div class="popup-design-preview w-full h-28 bg-gray-900 rounded flex items-center justify-center mb-2">
                                            <div class="loading-spinner-small"></div>
                                        </div>
                                        
                                        <div class="text-sm text-gray-400">
                                            ${d.width_mm ? `${d.width_mm.toFixed(0)} × ${d.height_mm?.toFixed(0) || 0} mm` : ''}
                                            ${d.color_count ? ` • ${d.color_count} colors` : ''}
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', popupHTML);
    
    // Load color image in popup (try multiple URLs)
    loadPopupColorImage(product);
    
    // Load design previews in popup
    loadPopupDesignPreviews();
}

// Load color image for popup, trying multiple URLs
async function loadPopupColorImage(product) {
    const imgElement = document.getElementById('popup-color-image');
    const placeholder = document.getElementById('popup-color-placeholder');
    
    if (!imgElement) return;
    
    try {
        const validUrl = await getValidColorImage(product);
        
        if (validUrl) {
            imgElement.src = validUrl;
            imgElement.style.display = '';
            if (placeholder) placeholder.style.display = 'none';
        } else {
            imgElement.style.display = 'none';
            if (placeholder) {
                placeholder.innerHTML = '<span class="text-gray-500">No preview</span>';
            }
        }
    } catch (e) {
        imgElement.style.display = 'none';
        if (placeholder) {
            placeholder.innerHTML = '<span class="text-gray-500">No preview</span>';
        }
    }
}

// Load design preview images in popup
async function loadPopupDesignPreviews() {
    const previewCards = document.querySelectorAll('.popup-design-card[data-json-url]');
    
    for (const card of previewCards) {
        const jsonUrl = card.dataset.jsonUrl;
        const imageContainer = card.querySelector('.popup-design-preview');
        
        // Skip if no valid URL
        if (!jsonUrl || jsonUrl === 'null' || jsonUrl === 'undefined' || jsonUrl === '') {
            imageContainer.innerHTML = `<span class="text-gray-600 text-xs">No file</span>`;
            continue;
        }
        
        try {
            const result = await eel.fetchDesignPreview(jsonUrl)();
            if (result && result.success && result.image_data) {
                imageContainer.innerHTML = `<img src="data:image/${result.format || 'png'};base64,${result.image_data}" class="w-full h-full object-contain rounded">`;
            } else {
                imageContainer.innerHTML = `<span class="text-gray-600 text-xs">No preview</span>`;
            }
        } catch (e) {
            imageContainer.innerHTML = `<span class="text-red-500 text-xs">Error</span>`;
        }
    }
}

function closeQCPopup() {
    const popup = document.getElementById('qc-popup');
    if (popup) popup.remove();
    
    // Stop recording when popup closes
    if (isRecording) {
        console.log('Popup closed - stopping recording');
        stopVideoRecording();
    }
}

async function confirmQCItem(itemId, orderId) {
    try {
        showToast('Đang xác nhận QC...', 'info');
        const result = await eel.activateQCItem(orderId, itemId)();
        
        if (result && result.success) {
            showToast(`✅ QC hoàn thành cho item ${itemId}`, 'success');
            closeQCPopup();
            // Refresh order
            await eel.searchOrder(orderId.toString())();
        } else {
            showToast(result?.message || 'Lỗi xác nhận QC', 'error');
        }
    } catch (e) {
        showToast('Lỗi kết nối', 'error');
    }
}

// ===== Handle QR Scan for QC =====
eel.expose(onQRScanned);
function onQRScanned(qrContent, trackData) {
    console.log('=== onQRScanned CALLED ===');
    console.log('userRole at scan time:', userRole);
    
    // Close any existing popup first
    closeQCPopup();
    
    // qrContent: https://manage.lemiex.us/track/20?stt=1&item_id=20
    // or malformed: https://manage.lemiex.us/track/20?stt=1&item_id=1?item_id=20
    // trackData: {success: true, data: {...}} from track API
    console.log('QR Scanned:', qrContent);
    console.log('Track data:', trackData);
    
    try {
        // Fix malformed URL with double ?
        let fixedUrl = qrContent;
        const questionMarks = (qrContent.match(/\?/g) || []).length;
        if (questionMarks > 1) {
            // Replace second ? with &
            const firstQ = qrContent.indexOf('?');
            fixedUrl = qrContent.substring(0, firstQ + 1) + qrContent.substring(firstQ + 1).replace('?', '&');
        }
        
        // Parse QR URL for order/item IDs
        const url = new URL(fixedUrl);
        const pathParts = url.pathname.split('/');
        const orderId = pathParts[pathParts.length - 1];
        const stt = url.searchParams.get('stt');
        
        // Get all item_id values (may have duplicates), use last one
        const allItemIds = url.searchParams.getAll('item_id');
        const itemId = allItemIds.length > 0 ? allItemIds[allItemIds.length - 1] : null;
        
        console.log(`QR Scanned - Order: ${orderId}, STT: ${stt}, Item: ${itemId}`);
        showToast(`📱 Scanned: Order #${orderId}, Item #${itemId}`, 'info');
        
        // Get role name using config helper (userRole can be object or string)
        const roleName = getRoleName(userRole);
        console.log('Current roleName:', roleName);
        
        // If track data is available, use it directly
        if (trackData && trackData.success && trackData.data) {
            const data = trackData.data;
            console.log('Track data.total_quantity:', data.total_quantity);
            console.log('Track data.items.length:', data.items?.length);
            
            // Pre-load label for Shipout role (optimization)
            if (LABEL_CONFIG.preload.enabled && LABEL_CONFIG.preload.onTrackResponse) {
                const labelUrl = data.order?.convert_label;
                if (labelUrl && canRoleDo(roleName, 'printLabel')) {
                    console.log('Pre-loading label for fast print...');
                    eel.preloadLabel(labelUrl)();  // Background download
                }
            }
            
            if (roleName === 'QC') {
                console.log('>>> Calling handleQCScanWithData...');
                handleQCScanWithData(data, orderId, itemId);
                return; // Stop here, don't continue
            } else if (roleName === 'Packing') {
                handlePackingScanWithData(data, orderId, itemId);
            } else if (roleName === 'Shipout') {
                handleShipoutScanWithData(data, orderId, itemId);
            } else {
                // Default: show item popup
                showTrackItemPopup(data, orderId, itemId);
            }
        } else {
            // Fallback to old behavior
            if (roleName === 'QC') {
                handleQCScan(orderId, stt, itemId);
            } else if (roleName === 'Packing') {
                handlePackingScan(orderId, stt, itemId);
            } else if (roleName === 'Shipout') {
                handleShipoutScan(orderId, stt, itemId);
            } else {
                eel.searchOrder(orderId)();
            }
        }
    } catch (e) {
        console.error('Invalid QR content:', qrContent, e);
        showToast('QR không hợp lệ', 'error');
    }
}

// Handle QC scan with track data
async function handleQCScanWithData(data, orderId, itemId) {
    try {
        console.log('=== handleQCScanWithData START ===');
        
        // === CHECK: If same item is being scanned again, stop recording and upload ===
        if (isRecording && recordingOrderId === String(orderId) && recordingItemId === String(itemId)) {
            console.log('Same item scanned again - stopping recording and uploading');
            stopVideoRecording();
            showToast('🎬 Đã dừng ghi hình và đang upload...', 'info');
            return; // Stop processing, just stop recording
        }
        
        // === If recording different item, stop current recording first ===
        if (isRecording) {
            console.log('Different item scanned - stopping previous recording');
            stopVideoRecording();
        }
        
        // data format from track API: { order: {...}, items: [...], total_quantity: N }
        const order = data.order || { id: orderId };
        const items = data.items || [];
        
        // Use total_quantity from API, but validate against items array
        // Some API responses may have items with quantity > 1
        let totalQuantity = data.total_quantity;
        if (!totalQuantity || totalQuantity < items.length) {
            // Calculate from items if API doesn't provide or is less than items count
            totalQuantity = items.reduce((sum, item) => sum + (item.quantity || 1), 0);
        }
        
        // Add items and total_quantity to order for display
        order.items = items;
        order.total_quantity = totalQuantity;
        
        console.log('=== ORDER TYPE DEBUG ===');
        console.log('data.total_quantity from API:', data.total_quantity);
        console.log('items.length:', items.length);
        console.log('Calculated totalQuantity:', totalQuantity);
        console.log('Order type:', totalQuantity >= 2 ? 'ĐƠN NHIỀU ÁO' : 'ĐƠN LẺ');
        
        // Find the specific item by itemId
        let item = items.find(i => String(i.id) === String(itemId)) || items[0] || { id: itemId };
        console.log('Item found:', item?.id, 'Designs:', item?.designs?.length);
        
        // === STEP 1: Hiện tổng đơn hàng phía sau (trước khi activate) ===
        displayOrderFromTrackData(order, items);
        
        // === STEP 2: Start video recording (via Python backend) ===
        if (autoRecordEnabled) {
            startVideoRecording(orderId, itemId);
        }
        
        // === STEP 3: Auto activate QC for all positions ===
        const designs = item.designs || [];
        const positions = designs.length > 0 ? designs.map(d => d.position) : ['front'];
        console.log('Positions to activate:', positions);
        
        showToast(`Đang xác nhận QC (${positions.length} vị trí)...`, 'info');
        
        // Run activate API and popup in parallel
        const activatePromise = (async () => {
            try {
                const activateResult = await eel.activateQCItem(orderId, item.id, positions)();
                console.log('QC activate result:', activateResult);
                if (activateResult && activateResult.success) {
                    showToast(`✅ QC đã xác nhận cho item ${item.id} (${positions.join(', ')})`, 'success');
                    return true;
                } else {
                    showToast(`⚠️ QC: ${activateResult?.message || 'Lỗi'}`, 'warning');
                    return false;
                }
            } catch (e) {
                console.error('QC activate error:', e);
                return false;
            }
        })();
        
        // === STEP 3: Show popup chi tiết item (parallel with activate) ===
        showQCItemPopup(item, order);
        
        // Wait for activate to complete
        const activateSuccess = await activatePromise;
        
        // === STEP 5: Re-fetch data after activate to update timeline ===
        if (activateSuccess) {
            console.log('Re-fetching data after activate...');
            try {
                // Build track URL to re-fetch
                const trackUrl = `https://manage.lemiex.us/track/${orderId}?item_id=${itemId}`;
                const freshData = await eel.getTrackData(trackUrl)();
                console.log('Fresh data after activate:', freshData);
                if (freshData && freshData.success && freshData.data) {
                    const freshOrder = freshData.data.order || { id: orderId };
                    const freshItems = freshData.data.items || [];
                    freshOrder.items = freshItems;
                    freshOrder.total_quantity = freshData.data.total_quantity || freshItems.length;
                    
                    // Update main view with fresh data (timeline should show updated status)
                    displayOrderFromTrackData(freshOrder, freshItems);
                    
                    // Update popup timeline in realtime (don't recreate popup)
                    const freshItem = freshItems.find(i => String(i.id) === String(itemId)) || freshItems[0];
                    if (freshItem && document.getElementById('qc-popup')) {
                        updatePopupTimeline(freshItem);
                        showToast('✅ Timeline đã cập nhật', 'success');
                    }
                    
                    // === MULTI ORDER: Check if this was the last item to QC ===
                    if (freshItems.length >= 2) {
                        // Check how many items have QC completed
                        const qcCompletedItems = freshItems.filter(item => {
                            const designs = item.designs || [];
                            return designs.some(d => d.qc_status === 1);
                        });
                        
                        console.log(`MULTI order check: ${qcCompletedItems.length}/${freshItems.length} items QC completed`);
                        
                        if (qcCompletedItems.length === freshItems.length) {
                            // All items are QC completed - this was the last one!
                            showMultiOrderCompleteNotification(freshOrder, freshItems.length);
                        } else {
                            // Show remaining items count
                            const remaining = freshItems.length - qcCompletedItems.length;
                            showToast(`📦 ĐƠN NHIỀU ÁO: Còn ${remaining}/${freshItems.length} items chưa QC`, 'info');
                        }
                    }
                }
            } catch (e) {
                console.error('Re-fetch error:', e);
            }
        }
        
        console.log('=== handleQCScanWithData END ===');
        
    } catch (err) {
        console.error('handleQCScanWithData ERROR:', err);
        showToast('Lỗi xử lý QC scan', 'error');
    }
}

// Display order from track API data
function displayOrderFromTrackData(order, items) {
    // Get elements using correct IDs from HTML
    const orderIdDisplay = document.getElementById('order-id-display');
    const refId = document.getElementById('ref-id');
    const trackingId = document.getElementById('tracking-id');
    const statusSelect = document.getElementById('order-status-select');
    const container = document.getElementById('items-container');
    const itemsCount = document.getElementById('items-count');
    
    // Skip if main elements don't exist
    if (!container) {
        console.log('displayOrderFromTrackData: items-container not found, skipping');
        return;
    }
    
    // Update order info
    if (orderIdDisplay) orderIdDisplay.textContent = `# ${order.id || '---'}`;
    if (refId) refId.textContent = `Ref: ${order.ref_id || '-'}`;
    if (trackingId) trackingId.textContent = `Tracking: ${order.tracking_id || '-'}`;
    
    // Set fulfill status
    const status = normalizeStatus(order.fulfill_status);
    if (statusSelect) {
        statusSelect.value = status;
        statusSelect.disabled = false;
        // Update status class
        statusSelect.className = statusSelect.className.replace(/status-\w+/g, '');
        statusSelect.classList.add(`status-${status}`);
    }
    
    // Determine SINGLE/MULTI using total_quantity
    // Use total_quantity from order, but validate against items array
    let totalQuantity = order.total_quantity;
    if (!totalQuantity || totalQuantity < items.length) {
        // Calculate from items: sum of all quantities
        totalQuantity = items.reduce((sum, item) => sum + (item.quantity || 1), 0);
    }
    const orderType = totalQuantity >= 2 ? 'ĐƠN NHIỀU ÁO' : 'ĐƠN LẺ';
    const orderTypeClass = totalQuantity >= 2 ? 'bg-warning' : 'bg-success';
    
    console.log('displayOrderFromTrackData - order.total_quantity:', order.total_quantity, 'items.length:', items.length, 'calculated totalQuantity:', totalQuantity, 'orderType:', orderType);

    // Add Timeline and Order Type to header (like displayOrder)
    // Look for the order header container or create timeline section
    let timelineSection = document.getElementById('order-timeline-section');
    const orderHeaderContainer = document.querySelector('#order-note-section')?.parentElement;
    
    if (!timelineSection && orderHeaderContainer) {
        timelineSection = document.createElement('div');
        timelineSection.id = 'order-timeline-section';
        timelineSection.className = 'px-4 pt-2';
        orderHeaderContainer.appendChild(timelineSection);
    }
    
    if (timelineSection) {
        timelineSection.innerHTML = `
            <div class="flex items-center justify-between bg-dark-100 mx-0 px-4 py-3 rounded-lg">
                <div class="flex items-center gap-4">
                    <span class="px-3 py-1 ${orderTypeClass} rounded-lg text-white font-bold">${orderType}</span>
                    <span class="text-gray-400">${items.length} item(s) | Total: ${totalQuantity}</span>
                </div>
                ${createTimelineHTML(order)}
            </div>
        `;
        console.log('Timeline section updated with orderType:', orderType);
    } else {
        console.warn('Could not find or create timeline section');
    }

    // Items display
    if (itemsCount) itemsCount.textContent = `(${items.length} items)`;

    if (items.length === 0) {
        container.innerHTML = '<div class="text-center text-gray-400 py-8">Không có sản phẩm</div>';
        return;
    }

    container.innerHTML = items.map((item, index) => {
        const product = item.product || {};
        const productName = product.product_name || item.product_name || 'Unknown Product';
        const style = product.style || item.style || '';
        const color = product.color || item.color || '';
        const size = product.size || item.size || '';
        
        return `
        <div class="product-card-new" data-item-index="${index}">
            <!-- Left: Color Image -->
            <div class="flex flex-col gap-3 items-center color-image-container">
                <img class="color-image w-60 h-60 rounded-lg object-cover border-2 border-gray-600" 
                     alt="${color}" 
                     style="display: none;"
                     onerror="this.style.display='none'">
                <div class="color-image-placeholder w-60 h-60 rounded-lg bg-gray-800 flex items-center justify-center border-2 border-gray-600">
                    <div class="loading-spinner-small"></div>
                </div>
            </div>
            
            <!-- Middle: Product Info -->
            <div class="flex-1 flex flex-col gap-3">
                <div class="text-lg font-bold text-white">${productName}</div>
                
                <!-- Product variant info with styled borders -->
                <div class="flex flex-wrap gap-3">
                    ${style ? `<span class="variant-badge variant-style px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-purple-400 bg-purple-600/80">📦 ${style}</span>` : ''}
                    ${color ? `<span class="variant-badge variant-color px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-blue-400 bg-blue-600/80">🎨 ${color}</span>` : ''}
                    ${size ? `<span class="variant-badge variant-size px-4 py-2 rounded-lg text-white font-bold text-base border-2 border-green-400 bg-green-600/80">📏 ${size}</span>` : ''}
                </div>
                
                <div class="flex gap-4 text-sm text-gray-400">
                    <span>Số lượng: <strong class="text-white">${item.quantity || 1}</strong></span>
                </div>
                
                <!-- Item Timeline -->
                <div class="mt-2">
                    ${createItemTimelineSmall(item)}
                </div>
            </div>
            
            <!-- Middle: Mockup Image -->
            <div class="flex flex-col gap-3">
                <img src="${item.mockup || 'https://via.placeholder.com/120'}" 
                     alt="${productName}" class="w-60 h-60 rounded-lg object-cover bg-gray-900"
                     onerror="this.src='https://via.placeholder.com/120?text=No+Image'">
            </div>
            
            <!-- Right: Design Previews -->
            <div class="flex flex-col gap-2">
                ${item.designs && item.designs.length > 0 ? `
                    <div class="text-sm text-gray-400 font-semibold mb-1">Designs (${item.designs.length}):</div>
                    <div class="flex gap-3">
                        ${item.designs.map((d, idx) => `
                            <div class="design-preview-card bg-gray-800 rounded-lg p-2 border border-gray-700" data-json-url="${d.json_url}" data-item-id="${item.id}" data-design-idx="${idx}">
                                <div class="text-xs text-center text-gray-400 mb-1 capitalize font-semibold">${d.position}</div>
                                <div class="design-preview-image w-28 h-28 bg-gray-900 rounded flex items-center justify-center">
                                    <div class="loading-spinner-small"></div>
                                </div>
                                <div class="text-xs text-gray-500 mt-1 text-center">
                                    ${d.stitch_count ? `${(d.stitch_count/1000).toFixed(1)}k st` : ''}
                                </div>
                                <div class="text-xs text-gray-500 text-center">
                                    ${d.width_mm ? `${d.width_mm.toFixed(0)}×${d.height_mm?.toFixed(0) || 0}mm` : ''}
                                </div>
                                ${d.color_count ? `<div class="text-xs text-gray-500 text-center">${d.color_count} colors</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                ` : '<div class="text-gray-500 text-sm">No designs</div>'}
            </div>
        </div>
    `}).join('');
    
    // Load color images async
    loadColorImagesForItems(items);
    
    // Load design previews
    loadDesignPreviews();
}

// Handle Packing scan with track data  
function handlePackingScanWithData(data, orderId, itemId) {
    const totalItems = data.items ? data.items.length : 1;
    
    // If different order, reset pending items (bỏ order cũ chưa scan đủ)
    if (packingOrderId !== null && packingOrderId !== orderId) {
        if (packingPendingItems.length > 0 && packingPendingItems.length < totalItems) {
            showToast(`⚠️ Bỏ order #${packingOrderId} (chưa scan đủ ${packingPendingItems.length} items)`, 'warning');
            // Stop any ongoing packing recording
            eel.stopPackingRecording()();
        }
        packingPendingItems = [];
        packingOrderId = orderId;
        // Clear pending UI
        updatePackingPendingUI(null);
    }
    
    if (packingOrderId === null) {
        packingOrderId = orderId;
    }
    
    // Find specific item
    let item = null;
    if (data.items && Array.isArray(data.items)) {
        item = data.items.find(i => String(i.id) === String(itemId));
    }
    if (!item) {
        item = data.items?.[0] || { id: itemId };
    }
    
    // Get item positions from designs
    const positions = item.designs ? item.designs.map(d => d.position) : ['front'];
    
    // Add to pending if not already there
    if (!packingPendingItems.find(i => i.itemId === itemId)) {
        // START RECORDING on first item scan
        if (packingPendingItems.length === 0) {
            // First item - start recording with calculated duration and first_item_id
            startPackingRecordingWithItems(orderId, totalItems, parseInt(itemId));
        }
        
        packingPendingItems.push({ 
            orderId, 
            itemId, 
            item, 
            positions,  // Include positions for API
            data, 
            scannedAt: new Date() 
        });
        showToast(`📦 Scan item ${packingPendingItems.length}/${totalItems}`, 'info');
        
        // Update pending UI with timeline
        updatePackingPendingUI(data.order || { id: orderId }, data.items, packingPendingItems);
    } else {
        showToast(`Item ${itemId} đã scan rồi`, 'warning');
        return;
    }
    
    // Check if all items scanned - auto activate without popup
    if (packingPendingItems.length >= totalItems) {
        // All items scanned - auto activate packing
        autoActivatePacking(orderId, data.order || { id: orderId });
    } else {
        showToast(`Còn ${totalItems - packingPendingItems.length} items chưa scan`, 'warning');
    }
}

// Update Packing Pending UI with timeline
function updatePackingPendingUI(order, allItems, scannedItems) {
    // Remove existing pending UI
    const existingUI = document.getElementById('packing-pending-ui');
    if (existingUI) existingUI.remove();
    
    if (!order || !scannedItems || scannedItems.length === 0) return;
    
    const totalItems = allItems ? allItems.length : 1;
    const scannedCount = scannedItems.length;
    
    // Create pending timeline UI
    const pendingHTML = `
        <div id="packing-pending-ui" class="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-dark-200 rounded-xl p-4 border-2 border-warning shadow-xl z-40">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                    <span class="text-2xl">📦</span>
                    <span class="font-bold text-lg">Packing Order #${order.id}</span>
                </div>
                <span class="px-3 py-1 bg-warning rounded-lg text-black font-bold">
                    ${scannedCount}/${totalItems}
                </span>
            </div>
            <div class="text-sm text-gray-400 mb-2">Items đã scan:</div>
            <div class="flex flex-wrap gap-2">
                ${scannedItems.map((s, idx) => `
                    <div class="flex items-center gap-2 bg-success/20 border border-success rounded-lg px-3 py-2">
                        <span class="text-success">✓</span>
                        <span class="text-white font-medium">Item ${s.item?.stt || idx + 1}</span>
                    </div>
                `).join('')}
                ${Array(totalItems - scannedCount).fill(0).map((_, idx) => `
                    <div class="flex items-center gap-2 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2">
                        <span class="text-gray-500">○</span>
                        <span class="text-gray-400">Chờ scan...</span>
                    </div>
                `).join('')}
            </div>
            <button onclick="cancelPackingPending()" class="mt-3 w-full bg-gray-600 hover:bg-gray-500 py-2 rounded-lg text-sm">
                Hủy
            </button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', pendingHTML);
}

// Cancel packing pending
function cancelPackingPending() {
    // Stop packing recording if active
    eel.stopPackingRecording()();
    
    packingPendingItems = [];
    packingOrderId = null;
    updatePackingPendingUI(null);
    showToast('Đã hủy packing', 'info');
}

// Start packing recording with calculated duration
async function startPackingRecordingWithItems(orderId, totalItems, firstItemId) {
    try {
        const result = await eel.startPackingRecording(orderId, totalItems, firstItemId)();
        if (result && result.success) {
            showToast(`🔴 Bắt đầu ghi hình Packing (${result.limit}s cho ${totalItems} items)`, 'info');
        } else {
            console.warn('Could not start packing recording:', result?.message);
        }
    } catch (e) {
        console.error('Start packing recording error:', e);
    }
}

// Auto activate packing when all items scanned (no popup)
async function autoActivatePacking(orderId, order) {
    try {
        showToast(`📦 Đang xử lý packing order #${orderId}...`, 'info');
        
        // Prepare items with positions for API
        const itemsWithPositions = packingPendingItems.map(i => ({
            item_id: i.itemId,
            positions: i.positions || ['front']
        }));
        
        const result = await eel.activatePackingItems(orderId, itemsWithPositions)();
        
        if (result && result.success) {
            showToast(`✅ Packing hoàn thành order #${orderId} (${itemsWithPositions.length} items)`, 'success');
            
            // Clear pending UI
            updatePackingPendingUI(null);
            
            // Reset for next order
            packingPendingItems = [];
            packingOrderId = null;
            
            // Refresh track data to update timeline
            await refreshTrackData(orderId);
        } else {
            showToast(result?.message || 'Lỗi packing', 'error');
        }
    } catch (e) {
        console.error('Packing error:', e);
        showToast('Lỗi kết nối', 'error');
    }
}

// Refresh track data after successful activation
async function refreshTrackData(orderId) {
    try {
        const trackUrl = `https://manage.lemiex.us/track/${orderId}`;
        const result = await eel.getTrackData(trackUrl)();
        
        if (result && result.success && result.data) {
            // Update main view with new data
            const order = result.data.order || { id: orderId };
            const items = result.data.items || [];
            
            // Refresh order display using existing function
            displayOrderFromTrackData(order, items);
            showToast('Timeline đã được cập nhật', 'info');
        }
    } catch (e) {
        console.error('Refresh track data error:', e);
    }
}

// Handle Shipout scan with track data - WAIT FOR ALL ITEMS before print
async function handleShipoutScanWithData(data, orderId, itemId) {
    console.log('=== handleShipoutScanWithData START ===');
    const order = data.order || { id: orderId };
    const items = data.items || [];
    const totalItems = items.length || 1;
    
    // If different order, reset pending items
    if (shipoutOrderId !== null && shipoutOrderId !== orderId) {
        if (shipoutPendingItems.length > 0 && shipoutPendingItems.length < totalItems) {
            showToast(`⚠️ Bỏ order #${shipoutOrderId} (chưa scan đủ ${shipoutPendingItems.length} items)`, 'warning');
        }
        shipoutPendingItems = [];
        shipoutOrderId = orderId;
        updateShipoutPendingUI(null);
    }
    
    if (shipoutOrderId === null) {
        shipoutOrderId = orderId;
    }
    
    // Find specific item
    let item = null;
    if (items && Array.isArray(items)) {
        item = items.find(i => String(i.id) === String(itemId));
    }
    if (!item) {
        item = items[0] || { id: itemId };
    }
    
    // Add to pending if not already there
    if (!shipoutPendingItems.find(i => i.itemId === itemId)) {
        shipoutPendingItems.push({
            orderId,
            itemId,
            item,
            data,
            scannedAt: new Date()
        });
        showToast(`🚚 Scan item ${shipoutPendingItems.length}/${totalItems}`, 'info');
        
        // Update pending UI
        updateShipoutPendingUI(order, items, shipoutPendingItems);
    } else {
        showToast(`Item ${itemId} đã scan rồi`, 'warning');
        return;
    }
    
    // ALWAYS display order details in main view
    displayOrderFromTrackData(order, items);
    
    // Store current order data for manual print button
    window.currentShipoutOrder = { order, items, labelUrl: order.convert_label };
    
    // Check if all items scanned - then print and activate
    if (shipoutPendingItems.length >= totalItems) {
        await autoActivateShipout(orderId, order, items);
    } else {
        showToast(`Còn ${totalItems - shipoutPendingItems.length} items chưa scan`, 'warning');
    }
}

// Auto activate shipout when all items scanned
async function autoActivateShipout(orderId, order, items) {
    try {
        const labelUrl = order.convert_label;
        const printerName = selectedPrinter || localStorage.getItem('selectedPrinter') || null;
        
        // Get role config for printing settings
        const roleName = getRoleName(userRole);
        const printingSettings = getPrintingSettings(roleName);
        
        // Check if can auto print
        const canAutoPrint = printingSettings.autoPrint && labelUrl && printerName;
        
        if (canAutoPrint) {
            showToast('🖨️ Đang in label...', 'info');
            
            // Print label first
            const printResult = await eel.printLabel(labelUrl, printerName)();
            
            if (printResult && printResult.success) {
                showToast(`✅ Label đã gửi đến ${printerName}`, 'success');
            } else {
                showToast(`⚠️ Lỗi in: ${printResult?.message || 'Unknown'} - Dùng nút Print thủ công`, 'warning');
            }
        } else {
            if (!labelUrl) {
                showToast('⚠️ Không tìm thấy label để in', 'warning');
            } else if (!printerName) {
                showToast('⚠️ Chưa chọn máy in trong Settings', 'warning');
            }
        }
        
        // Activate shipout for all items
        showToast('🚚 Đang xử lý shipout...', 'info');
        
        const result = await eel.activateShipoutOrder(orderId, items)();
        
        if (result && result.success) {
            const successCount = result.results?.filter(r => r.success).length || 0;
            const totalCount = result.results?.length || 0;
            showToast(`✅ Shipout hoàn thành (${successCount}/${totalCount} positions)`, 'success');
            
            // Clear pending UI
            updateShipoutPendingUI(null);
            
            // Reset state for next order
            shipoutPendingItems = [];
            shipoutOrderId = null;
            
            // Refresh track data
            await refreshTrackData(orderId);
        } else {
            showToast(result?.message || 'Lỗi shipout', 'error');
        }
        
    } catch (e) {
        console.error('Auto shipout error:', e);
        showToast('Lỗi xử lý shipout', 'error');
    }
}

// Update Shipout Pending UI with timeline
function updateShipoutPendingUI(order, allItems, scannedItems) {
    // Remove existing pending UI
    const existingUI = document.getElementById('shipout-pending-ui');
    if (existingUI) existingUI.remove();
    
    if (!order || !scannedItems || scannedItems.length === 0) return;
    
    const totalItems = allItems ? allItems.length : 1;
    const scannedCount = scannedItems.length;
    
    // Create pending timeline UI
    const pendingHTML = `
        <div id="shipout-pending-ui" class="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:w-96 bg-dark-200 rounded-xl p-4 border-2 border-purple shadow-xl z-40">
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-2">
                    <span class="text-2xl">🚚</span>
                    <span class="font-bold text-lg">Shipout Order #${order.id}</span>
                </div>
                <span class="px-3 py-1 bg-purple rounded-lg text-white font-bold">
                    ${scannedCount}/${totalItems}
                </span>
            </div>
            <div class="text-sm text-gray-400 mb-2">Items đã scan:</div>
            <div class="flex flex-wrap gap-2">
                ${scannedItems.map((s, idx) => `
                    <div class="flex items-center gap-2 bg-purple/20 border border-purple rounded-lg px-3 py-2">
                        <span class="text-purple">✓</span>
                        <span class="text-white font-medium">Item ${s.item?.stt || idx + 1}</span>
                    </div>
                `).join('')}
                ${Array(totalItems - scannedCount).fill(0).map((_, idx) => `
                    <div class="flex items-center gap-2 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2">
                        <span class="text-gray-500">○</span>
                        <span class="text-gray-400">Chờ scan...</span>
                    </div>
                `).join('')}
            </div>
            <button onclick="cancelShipoutPending()" class="mt-3 w-full bg-gray-600 hover:bg-gray-500 py-2 rounded-lg text-sm">
                Hủy
            </button>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', pendingHTML);
}

// Cancel shipout pending
function cancelShipoutPending() {
    shipoutPendingItems = [];
    shipoutOrderId = null;
    updateShipoutPendingUI(null);
    showToast('Đã hủy shipout', 'info');
}

// Show/hide Print Label button in header for Shipout role
function showShipoutActionButtons(order) {
    const btnPrintLabel = document.getElementById('btn-print-label');
    if (!btnPrintLabel) return;
    
    const labelUrl = order.convert_label;
    
    // Use config helper
    const roleName = getRoleName(userRole);
    
    // Show button if role can print and has label
    if (labelUrl && canRoleDo(roleName, 'printLabel')) {
        btnPrintLabel.classList.remove('hidden');
    } else {
        btnPrintLabel.classList.add('hidden');
    }
}

// Manual print label function (also activates shipout)
async function manualPrintLabel() {
    const data = window.currentShipoutOrder;
    if (!data || !data.labelUrl) {
        showToast('Không có label để in', 'warning');
        return;
    }
    
    const printerName = selectedPrinter || localStorage.getItem('selectedPrinter');
    
    if (!printerName) {
        showToast('Vui lòng chọn máy in trong Settings trước!', 'warning');
        return;
    }
    
    showToast('🖨️ Đang in label...', 'info');
    
    try {
        // Print label
        const printResult = await eel.printLabel(data.labelUrl, printerName)();
        
        if (printResult && printResult.success) {
            showToast(`✅ Label đã gửi đến ${printerName}`, 'success');
        } else {
            showToast(`⚠️ Lỗi in: ${printResult?.message || 'Unknown'}`, 'warning');
        }
        
        // Also activate shipout (same as auto-scan)
        showToast('🚚 Đang xử lý shipout...', 'info');
        
        const result = await eel.activateShipoutOrder(data.order.id, data.items)();
        
        if (result && result.success) {
            const successCount = result.results?.filter(r => r.success).length || 0;
            const totalCount = result.results?.length || 0;
            showToast(`✅ Shipout hoàn thành (${successCount}/${totalCount} positions)`, 'success');
            
            // Refresh track data
            await refreshTrackData(data.order.id);
        } else {
            showToast(result?.message || 'Lỗi shipout', 'error');
        }
        
    } catch (e) {
        console.error('Manual print error:', e);
        showToast('❌ Lỗi in label', 'error');
    }
}

// Shipout confirmation popup with label preview and printer selection
async function showShipoutConfirmPopup(items, order, labelUrl) {
    // Get available printers
    let printers = [];
    try {
        const printerResult = await eel.getConnectedPrinters()();
        if (printerResult && printerResult.success) {
            printers = printerResult.printers || [];
        }
    } catch (e) {
        console.error('Error getting printers:', e);
    }
    
    const totalItems = items.length;
    
    // Get saved printer from settings
    const savedPrinter = selectedPrinter || localStorage.getItem('selectedPrinter') || '';
    
    const popupHTML = `
        <div id="shipout-popup" class="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-4 overflow-y-auto">
            <div class="bg-dark-200 rounded-2xl p-6 max-w-2xl w-full">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-3">
                        <span class="text-4xl">🚚</span>
                        <div>
                            <h2 class="text-xl font-bold">Shipout Order #${order.id}</h2>
                            <p class="text-gray-400 text-sm">${totalItems} items sẽ được activate</p>
                        </div>
                    </div>
                    <button onclick="closeShipoutPopup()" class="text-gray-400 hover:text-white text-2xl">✕</button>
                </div>
                
                ${labelUrl ? `
                <!-- Label Preview -->
                <div class="mb-4 bg-white rounded-lg p-2 text-center">
                    <img src="${labelUrl}" alt="Shipping Label" class="max-h-64 mx-auto" onerror="this.parentElement.innerHTML='<div class=\\'text-gray-500 py-8\\'>Không thể tải label</div>'"/>
                </div>
                ` : `
                <div class="mb-4 bg-gray-700 rounded-lg p-8 text-center text-gray-400">
                    <span class="text-4xl">📄</span>
                    <p class="mt-2">Không có label để in</p>
                </div>
                `}
                
                <!-- Printer Selection -->
                <div class="mb-4">
                    <label class="block text-sm text-gray-400 mb-2">🖨️ Chọn máy in:</label>
                    <select id="printer-select" class="w-full bg-dark-300 border border-gray-600 rounded-lg px-4 py-3 text-white">
                        ${printers.length === 0 ? 
                            '<option value="">Không tìm thấy máy in</option>' :
                            `<option value="">-- Chọn máy in --</option>
                            ${printers.map(p => `
                                <option value="${p.name}" ${p.status === 'Ready' ? '' : 'disabled'} ${savedPrinter === p.name ? 'selected' : ''}>
                                    ${p.name} ${p.status === 'Ready' ? '✓' : '(Offline)'}
                                </option>
                            `).join('')}`
                        }
                    </select>
                </div>
                
                <!-- Items to Activate -->
                <div class="mb-4 max-h-32 overflow-y-auto">
                    <div class="text-sm text-gray-400 mb-2">Items sẽ activate:</div>
                    <div class="flex flex-wrap gap-2">
                        ${items.map((item, idx) => {
                            const positions = item.designs ? item.designs.map(d => d.position).join(', ') : 'front';
                            return `
                            <div class="bg-dark-300 border border-gray-600 rounded-lg px-3 py-2 text-sm">
                                <span class="text-white">Item ${item.stt || idx + 1}</span>
                                <span class="text-gray-500">(${positions})</span>
                            </div>
                            `;
                        }).join('')}
                    </div>
                </div>
                
                <!-- Actions -->
                <div class="flex gap-3">
                    <button onclick="closeShipoutPopup()" class="flex-1 bg-gray-600 hover:bg-gray-500 py-3 rounded-lg font-bold">
                        Hủy
                    </button>
                    ${labelUrl ? `
                    <button onclick="confirmShipoutWithPrint(${order.id}, '${labelUrl}')" class="flex-1 bg-success hover:bg-green-600 py-3 rounded-lg font-bold flex items-center justify-center gap-2">
                        🖨️ In Label & Shipout
                    </button>
                    ` : `
                    <button onclick="confirmShipoutOnly(${order.id})" class="flex-1 bg-primary hover:bg-blue-600 py-3 rounded-lg font-bold">
                        ✅ Xác nhận Shipout
                    </button>
                    `}
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', popupHTML);
    
    // Store items data for confirmation
    window._shipoutItems = items;
}

function closeShipoutPopup() {
    const popup = document.getElementById('shipout-popup');
    if (popup) popup.remove();
    window._shipoutItems = null;
}

// Shipout with print label
async function confirmShipoutWithPrint(orderId, labelUrl) {
    try {
        const printerSelect = document.getElementById('printer-select');
        const printerName = printerSelect?.value || null;
        
        if (!printerName) {
            showToast('⚠️ Vui lòng chọn máy in', 'warning');
            return;
        }
        
        showToast('🖨️ Đang in label...', 'info');
        
        // Print label first
        const printResult = await eel.printLabel(labelUrl, printerName)();
        
        if (printResult && printResult.success) {
            showToast('✅ Label đã gửi đến máy in', 'success');
        } else {
            showToast(`⚠️ Lỗi in: ${printResult?.message || 'Unknown'}`, 'warning');
        }
        
        // Then activate shipout for all items
        await confirmShipoutOnly(orderId);
        
    } catch (e) {
        console.error('Shipout with print error:', e);
        showToast('Lỗi in label', 'error');
    }
}

// Shipout only (no print)
async function confirmShipoutOnly(orderId) {
    try {
        const items = window._shipoutItems || [];
        
        if (items.length === 0) {
            showToast('⚠️ Không có items để activate', 'warning');
            return;
        }
        
        showToast('🚚 Đang xử lý shipout...', 'info');
        
        const result = await eel.activateShipoutOrder(orderId, items)();
        
        if (result && result.success) {
            const successCount = result.results?.filter(r => r.success).length || 0;
            const totalCount = result.results?.length || 0;
            showToast(`✅ Shipout hoàn thành (${successCount}/${totalCount} positions)`, 'success');
            closeShipoutPopup();
            
            // Refresh track data
            await refreshTrackData(orderId);
        } else {
            showToast(result?.message || 'Lỗi shipout', 'error');
        }
    } catch (e) {
        console.error('Shipout error:', e);
        showToast('Lỗi kết nối', 'error');
    }
}

async function confirmShipout(orderId, itemId) {
    try {
        showToast('Đang xử lý shipout...', 'info');
        const result = await eel.activateShipoutItem(orderId, itemId)();
        if (result && result.success) {
            showToast(`✅ Shipout hoàn thành cho item ${itemId}`, 'success');
            closeShipoutPopup();
        } else {
            showToast(result?.message || 'Lỗi shipout', 'error');
        }
    } catch (e) {
        showToast('Lỗi kết nối', 'error');
    }
}

// Show item popup for default role
function showTrackItemPopup(data, orderId, itemId) {
    const order = data.order || { id: orderId };
    
    // Find specific item
    let item = null;
    if (data.items && Array.isArray(data.items)) {
        item = data.items.find(i => String(i.id) === String(itemId));
    }
    if (!item) {
        item = data.items?.[0] || { id: itemId };
    }
    
    showQCItemPopup(item, order); // Reuse QC popup for viewing
}

async function handleQCScan(orderId, stt, itemId) {
    try {
        // First load the order to get item details
        const orderData = await eel.getOrderWithItem(orderId, itemId)();
        
        if (orderData && orderData.order && orderData.item) {
            // Show QC popup for this specific item
            showQCItemPopup(orderData.item, orderData.order);
        } else {
            showToast('Không tìm thấy item', 'error');
        }
    } catch (e) {
        showToast('Lỗi tải thông tin item', 'error');
    }
}

// ===== Packing Mode =====
async function handlePackingScan(orderId, stt, itemId) {
    // Load order data first to get total items and positions
    const orderData = await eel.getOrderData(orderId)();
    const items = orderData?.items || [];
    const totalItems = items.length || 1;
    
    // Find current item
    const item = items.find(i => String(i.id) === String(itemId)) || { id: itemId };
    const positions = item.designs ? item.designs.map(d => d.position) : ['front'];
    
    // If different order, reset pending items (bỏ order cũ chưa scan đủ)
    if (packingOrderId !== null && packingOrderId !== orderId) {
        if (packingPendingItems.length > 0) {
            showToast(`⚠️ Bỏ order #${packingOrderId} (chưa scan đủ)`, 'warning');
            // Stop any ongoing packing recording
            eel.stopPackingRecording()();
        }
        packingPendingItems = [];
        packingOrderId = orderId;
        updatePackingPendingUI(null);
    }
    
    if (packingOrderId === null) {
        packingOrderId = orderId;
    }
    
    // Add item to pending list if not already there
    if (!packingPendingItems.find(i => i.itemId === itemId)) {
        // START RECORDING on first item scan
        if (packingPendingItems.length === 0) {
            // First item - start recording with calculated duration and first_item_id
            startPackingRecordingWithItems(orderId, totalItems, parseInt(itemId));
        }
        
        packingPendingItems.push({ 
            orderId, 
            stt, 
            itemId, 
            item,
            positions,
            scannedAt: new Date() 
        });
        showToast(`📦 Scan item ${packingPendingItems.length}/${totalItems}`, 'info');
        
        // Update pending UI
        updatePackingPendingUI(orderData, items, packingPendingItems);
    } else {
        showToast(`Item ${itemId} đã scan rồi`, 'warning');
        return;
    }
    
    // Check if all items scanned - auto activate without popup
    if (packingPendingItems.length >= totalItems) {
        autoActivatePacking(orderId, orderData);
    } else {
        showToast(`Còn ${totalItems - packingPendingItems.length} items chưa scan`, 'warning');
    }
}

function showPackingConfirmPopup(order) {
    const popupHTML = `
        <div id="packing-popup" class="fixed inset-0 bg-black/90 z-50 flex items-center justify-center p-8">
            <div class="bg-dark-200 rounded-2xl p-8 max-w-md text-center">
                <div class="text-6xl mb-4">📦</div>
                <h2 class="text-2xl font-bold mb-4">Xác nhận đóng gói</h2>
                <p class="text-gray-400 mb-6">Order #${order.id} - ${packingPendingItems.length} items</p>
                <div class="flex gap-4">
                    <button onclick="cancelPacking()" class="flex-1 bg-gray-600 hover:bg-gray-500 py-3 rounded-lg font-bold">
                        Hủy
                    </button>
                    <button onclick="confirmPacking(${order.id})" class="flex-1 bg-success hover:bg-green-600 py-3 rounded-lg font-bold">
                        Xác nhận
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', popupHTML);
}

function cancelPacking() {
    packingPendingItems = [];
    packingOrderId = null;
    const popup = document.getElementById('packing-popup');
    if (popup) popup.remove();
    showToast('Đã hủy đóng gói', 'info');
}

async function confirmPacking(orderId) {
    try {
        const result = await eel.activatePackingItems(orderId, packingPendingItems.map(i => i.itemId))();
        if (result && result.success) {
            showToast('✅ Đóng gói hoàn thành', 'success');
            packingPendingItems = [];
            packingOrderId = null;
        } else {
            showToast(result?.message || 'Lỗi đóng gói', 'error');
        }
    } catch (e) {
        showToast('Lỗi kết nối', 'error');
    }
    const popup = document.getElementById('packing-popup');
    if (popup) popup.remove();
}

async function handleShipoutScan(orderId, stt, itemId) {
    // Shipout: directly activate
    try {
        const result = await eel.activateShipoutItem(orderId, itemId)();
        if (result && result.success) {
            showToast(`✅ Shipout hoàn thành cho item ${itemId}`, 'success');
        } else {
            showToast(result?.message || 'Lỗi shipout', 'error');
        }
    } catch (e) {
        showToast('Lỗi kết nối', 'error');
    }
}

// ===== Utilities =====
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slide-out 0.3s ease forwards';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}
