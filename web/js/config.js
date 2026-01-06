/**
 * Role-based Configuration for Lemiex QC App
 * Dễ dàng điều chỉnh chức năng cho từng role
 */

// =============================================================================
// API ENDPOINTS
// =============================================================================
const API_CONFIG = {
    BASE_URL: 'https://manage.lemiex.us',
    
    ENDPOINTS: {
        // Auth
        login: '/api/auth/login',
        logout: '/api/auth/logout',
        me: '/api/auth/me',
        
        // Orders
        orders: '/api/orders',
        orderDetail: '/api/orders/{order_id}',
        track: '/api/orders/track/{order_id}',
        
        // Status & Actions
        changeStatusItems: '/api/orders/change-status-items',
        qcReject: '/api/orders/qc-reject',
        uploadVideo: '/api/orders/upload-video',
        
        // Label
        updateLabel: '/api/orders/update-label',
    },
    
    // API settings
    TIMEOUT: 10000,  // 10 seconds
    RETRY_COUNT: 3,
};

// =============================================================================
// ROLE DEFINITIONS
// =============================================================================
const ROLES_CONFIG = {
    QC: {
        name: 'QC',
        displayName: 'Kiểm tra chất lượng',
        color: '#10B981',  // Green
        icon: '✓',
        
        // Chức năng được phép
        features: {
            scanQR: true,
            viewOrder: true,
            recordVideo: true,
            uploadVideo: true,
            activatePositions: true,
            rejectItem: true,
            printLabel: false,
        },
        
        // Recording settings
        recording: {
            enabled: true,
            baseDuration: 15,      // Giây cơ bản
            perItemDuration: 10,   // Thêm mỗi item
            autoStart: true,
            autoUpload: true,
        },
        
        // Positions to activate
        activatePositions: ['front', 'back', 'sleeve_left', 'sleeve_right', 'neck'],
    },
    
    Packing: {
        name: 'Packing',
        displayName: 'Đóng gói',
        color: '#F59E0B',  // Orange
        icon: '📦',
        
        features: {
            scanQR: true,
            viewOrder: true,
            recordVideo: true,
            uploadVideo: true,
            activatePositions: true,
            rejectItem: false,
            printLabel: false,
        },
        
        recording: {
            enabled: true,
            baseDuration: 15,
            perItemDuration: 10,
            autoStart: true,
            autoUpload: true,
        },
        
        // Packing activate 1 position cho tất cả items
        activatePositions: ['front'],
    },
    
    Shipout: {
        name: 'Shipout',
        displayName: 'Xuất hàng',
        color: '#3B82F6',  // Blue
        icon: '🚚',
        
        features: {
            scanQR: true,
            viewOrder: true,
            recordVideo: false,
            uploadVideo: false,
            activatePositions: true,
            rejectItem: false,
            printLabel: true,
        },
        
        recording: {
            enabled: false,
        },
        
        // Shipout activate tất cả để đánh dấu shipped
        activatePositions: ['front', 'back', 'sleeve_left', 'sleeve_right', 'neck'],
        
        // Printing settings
        printing: {
            autoPrint: true,
            preloadLabel: true,
            retryOnFail: true,
            maxRetries: 2,
        },
    },
    
    Admin: {
        name: 'Admin',
        displayName: 'Quản trị viên',
        color: '#EF4444',  // Red
        icon: '👑',
        
        features: {
            scanQR: true,
            viewOrder: true,
            recordVideo: true,
            uploadVideo: true,
            activatePositions: true,
            rejectItem: true,
            printLabel: true,
            manageSettings: true,
        },
        
        recording: {
            enabled: true,
            baseDuration: 15,
            perItemDuration: 10,
            autoStart: true,
            autoUpload: true,
        },
        
        activatePositions: ['front', 'back', 'sleeve_left', 'sleeve_right', 'neck'],
        
        printing: {
            autoPrint: false,
            preloadLabel: true,
        },
    },
};

// =============================================================================
// COMMON SETTINGS
// =============================================================================
const COMMON_CONFIG = {
    // Order display
    orderDisplay: {
        showMockup: true,
        showColorImage: true,
        showTimeline: true,
        multiOrderWarning: true,
        multiOrderLabel: 'ĐƠN NHIỀU ÁO',
        singleOrderLabel: 'ĐƠN LẺ',
    },
    
    // Label settings
    label: {
        cacheEnabled: true,
        preloadOnScan: true,
        printTimeout: 15000,
    },
    
    // Scanner settings
    scanner: {
        debounceMs: 500,  // Tránh scan trùng
    },
    
    // UI settings
    ui: {
        theme: 'dark',
        language: 'vi',
        toastDuration: 3000,
        animationEnabled: true,
    },
};

// =============================================================================
// LABEL OPTIMIZATION CONFIG
// =============================================================================
const LABEL_CONFIG = {
    // Pre-download strategy
    preload: {
        enabled: true,
        onTrackResponse: true,    // Download ngay khi có track data
        backgroundDownload: true, // Không blocking UI
    },
    
    // Print settings
    print: {
        paperSize: '4x6',
        noMargins: true,
        autoFit: true,
        portrait: true,
        timeout: 15000,
    },
    
    // Fallback
    fallback: {
        showManualButton: true,
    },
};

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Lấy config cho role
 */
function getRoleConfig(roleName) {
    return ROLES_CONFIG[roleName] || ROLES_CONFIG.QC;
}

/**
 * Lấy features của role
 */
function getRoleFeatures(roleName) {
    const role = getRoleConfig(roleName);
    return role.features || {};
}

/**
 * Kiểm tra role có quyền làm feature không
 */
function canRoleDo(roleName, feature) {
    const features = getRoleFeatures(roleName);
    return features[feature] === true;
}

/**
 * Lấy recording settings cho role
 */
function getRecordingSettings(roleName) {
    const role = getRoleConfig(roleName);
    return role.recording || { enabled: false };
}

/**
 * Lấy printing settings cho role
 */
function getPrintingSettings(roleName) {
    const role = getRoleConfig(roleName);
    return role.printing || { autoPrint: false };
}

/**
 * Lấy positions cần activate cho role
 */
function getActivatePositions(roleName) {
    const role = getRoleConfig(roleName);
    return role.activatePositions || [];
}

/**
 * Lấy API endpoint URL đầy đủ
 */
function getApiEndpoint(name, params = {}) {
    let endpoint = API_CONFIG.ENDPOINTS[name] || '';
    for (const [key, value] of Object.entries(params)) {
        endpoint = endpoint.replace(`{${key}}`, value);
    }
    return `${API_CONFIG.BASE_URL}${endpoint}`;
}

/**
 * Lấy role name từ userRole (có thể là object hoặc string)
 */
function getRoleName(userRole) {
    if (!userRole) return 'QC';
    return typeof userRole === 'object' ? userRole.name : userRole;
}

// Export for use in app.js
if (typeof window !== 'undefined') {
    window.ROLES_CONFIG = ROLES_CONFIG;
    window.COMMON_CONFIG = COMMON_CONFIG;
    window.LABEL_CONFIG = LABEL_CONFIG;
    window.API_CONFIG = API_CONFIG;
    
    window.getRoleConfig = getRoleConfig;
    window.getRoleFeatures = getRoleFeatures;
    window.canRoleDo = canRoleDo;
    window.getRecordingSettings = getRecordingSettings;
    window.getPrintingSettings = getPrintingSettings;
    window.getActivatePositions = getActivatePositions;
    window.getApiEndpoint = getApiEndpoint;
    window.getRoleName = getRoleName;
}
