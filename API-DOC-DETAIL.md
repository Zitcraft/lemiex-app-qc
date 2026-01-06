# API Documentation (Chi tiết)

Base URL: `/api`

---

## 🔐 Auth

### POST `/auth/login`
Đăng nhập

**Body (raw JSON):**
```json
{
    "email": "seller.gold@example.com",
    "password": "password"
}
```

### POST `/auth/logout`
Đăng xuất (không cần body)

### GET `/auth/me`
Lấy thông tin user hiện tại (không cần params)

---

## 👥 Users (admin only)

### GET `/users`
Danh sách users

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang (default: 10) |
| search | string | Tìm theo email, username, first_name, last_name |
| status | string | Unconfirmed, Active, Banned |
| role_id | int | ID của role |
| tier | int | 0/1 (private_seller) |

### POST `/users`
Tạo user mới

**Body (raw JSON):**
```json
{
    "email": "user@example.com",
    "username": "username123",
    "password": "password123",
    "password_confirmation": "password123",
    "role_id": 3,
    "status": "Active",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "0123456789",
    "address": "123 Street",
    "birthday": "1990-01-01",
    "webhook_url": "https://example.com/webhook",
    "telegram_id": "123456789",
    "private_seller": true,
    "max_debit": 1000,
    "max_date_debit": 30,
    "min_date_debit": 7
}
```

### GET `/users/{id}`
Chi tiết user

### PUT `/users/{id}`
Cập nhật user

**Body (raw JSON):**
```json
{
    "email": "user@example.com",
    "username": "username123",
    "role_id": 3,
    "status": "Active",
    "first_name": "John",
    "last_name": "Doe",
    "phone": "0123456789",
    "private_seller": true,
    "max_debit": 1000
}
```

### DELETE `/users/{id}`
Xóa user

---

## 📦 Orders

### POST `/update-label` ⚠️ Webhook (không cần auth)
Webhook cập nhật label từ bên ngoài

**Body (raw JSON):**
```json
{
    "order_id": 123,
    "tracking_id": "1Z999AA10123456784",
    "tracking_link": "https://tracking.example.com/1Z999AA10123456784",
    "label_url": "https://example.com/label.pdf"
}
```

### GET `/orders/update-label`
Cập nhật label (internal)

### GET `/orders`
Danh sách đơn hàng

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang (default: 20) |
| page | int | Trang (default: 1) |
| ref_id | string | Tìm theo ref_id |
| seller_ref | string | Tìm theo seller_ref |
| order_stt | string | Tìm theo order_stt (nhiều ID cách nhau bởi dấu cách/phẩy) |
| fulfill_status | string/array | pending, processing, qc_pass, packed, shipped, delivered, cancelled |
| payment_status | string/array | pending, paid, failed |
| processing_status | string | processing status |
| seller_id | int | ID seller |
| store_id | int | ID store |
| date_from | date | Từ ngày (YYYY-MM-DD) |
| date_to | date | Đến ngày (YYYY-MM-DD) |
| cost_min | float | Chi phí tối thiểu |
| cost_max | float | Chi phí tối đa |
| search | string | Tìm chung (ref_id, seller_ref, order_stt, tracking_id) |
| sort_by | string | Sắp xếp theo field (default: created_at) |
| sort_order | string | asc/desc (default: desc) |

### POST `/orders/create`
Tạo đơn hàng (cần middleware: seller)

**Body (raw JSON) - NO_DESIGN:**
```json
{
    "api_key": "store_api_key_here",
    "order_type": "NO_DESIGN",
    "ref_id": "ORDER-12345",
    "seller_ref": "SELLER-REF-123",
    "order_status": "pending",
    "shipping_method": "standard",
    "shipping_service": "usps",
    "note": "Order note",
    "address": {
        "name": "John Doe",
        "phone": "1234567890",
        "street1": "123 Main St",
        "street2": "Apt 4B",
        "city": "New York",
        "state": "NY",
        "zip": "10001",
        "country": "US"
    },
    "line_items": [
        {
            "variant_id": "VARIANT-001",
            "quantity": 2,
            "mockup": "https://example.com/mockup.jpg",
            "mockup_back": "https://example.com/mockup-back.jpg",
            "design_front": "https://example.com/design-front.png",
            "design_back": "https://example.com/design-back.png"
        }
    ]
}
```

**Body (raw JSON) - LABEL_SHIP:**
```json
{
    "api_key": "store_api_key_here",
    "order_type": "LABEL_SHIP",
    "ref_id": "ORDER-12345",
    "seller_ref": "SELLER-REF-123",
    "order_status": "pending",
    "shipping_method": "standard",
    "shipping_service": "usps",
    "shipping_label": "https://example.com/label.pdf",
    "fulfillment_priority": "normal",
    "note": "Order note",
    "line_items": [...]
}
```

### PUT `/orders/update`
Cập nhật đơn hàng

### GET `/orders/fulfill-statuses`
Danh sách fulfill statuses (không cần params)

### PUT `/orders/change-fulfill-status`
Đổi fulfill status (cần middleware: staff)

**Body (raw JSON):**
```json
{
    "order_id": 123,
    "fulfill_status": "processing"
}
```
Fulfill status values: `pending`, `processing`, `qc_pass`, `packed`, `shipped`, `delivered`, `cancelled`

### PUT `/orders/change-status-items`
Đổi status items

**Body (raw JSON):**
```json
{
    "item_id": 123,
    "meta_key": "front",
    "status": true
}
```
meta_key values: `front`, `back`, `sleeve_left`, `sleeve_right`, `neck`

### PUT `/orders/qc-reject`
QC reject item

**Body (raw JSON):**
```json
{
    "item_id": 123
}
```

### POST `/orders/post-label`
Post label

### GET `/orders/track/{orderId}`
Tracking đơn hàng

### GET `/orders/{id}`
Chi tiết đơn hàng

### GET `/orders/{id}/timeline`
Timeline đơn hàng

### GET `/orders/{id}/qr-codes`
QR codes đơn hàng

### PUT `/orders/remake/file`
Remake file

### PUT `/orders/remake/qr`
Remake QR

### GET `/proxy/shipping-label`
Proxy shipping label (tránh CORS)

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| url | string | URL của shipping label |

---

## 🏪 Stores

### GET `/stores`
Danh sách stores (simple - cho dropdown)

### GET `/stores/list`
Danh sách stores với pagination

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang |
| page | int | Trang |
| search | string | Tìm kiếm |
| status | string | Active/Inactive |
| sort_by | string | Sắp xếp theo |
| sort_order | string | asc/desc |

### GET `/stores/users`
Danh sách users cho tạo store

### POST `/stores`
Tạo store

**Body (raw JSON):**
```json
{
    "user_id": 5,
    "name": "My Store",
    "api_key": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```
Note: api_key phải đúng 32 ký tự, chỉ chữ và số

### PUT `/stores/{id}`
Cập nhật store

**Body (raw JSON):**
```json
{
    "user_id": 5,
    "name": "My Store Updated",
    "api_key": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "status": "Active"
}
```

### GET `/stores/{id}`
Chi tiết store

---

## 🛍️ Products

### GET `/products`
Danh sách products

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| status | boolean | true/false |
| search | string | Tìm theo tên |

### POST `/products`
Tạo product

**Body (raw JSON):**
```json
{
    "name": "T-Shirt Classic",
    "style": "Classic",
    "status": true,
    "mockup": "https://example.com/mockup.jpg",
    "brand": "Brand Name",
    "warehouse_name": "Warehouse A",
    "variants": [
        {
            "variant_id": "TSHIRT-BLK-M",
            "sku": "SKU-001",
            "style": "Classic",
            "color": "Black",
            "size": "M",
            "stock": 100,
            "active": true,
            "weight": 200,
            "length": 30,
            "width": 20,
            "height": 2,
            "supplier_price": 5.99,
            "prices": [
                {"tier_id": 0, "type": "base_cost", "price": 8.99},
                {"tier_id": 0, "type": "front", "price": 2.00},
                {"tier_id": 1, "type": "base_cost", "price": 7.99}
            ]
        }
    ]
}
```
tier_id: 0=Silver, 1=Gold, 2=Platinum, 3=Diamond
type: `base_cost`, `front`, `back`, `sleeve_left`, `sleeve_right`, `special`, `seller_shipping`, `tiktok_shipping`, `priority_shipping`, `additional_standard`, `additional_priority`, `shipping_cost`

### GET `/products/filter-options`
Filter options

### GET `/products/metadata`
Metadata (tiers, price_types)

### GET `/products/variants`
Danh sách variants

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| search | string | Tìm theo variant_id, sku, style, color, product name |
| product_id | int | Filter theo product |
| color | string | Filter theo color |
| size | string | Filter theo size |
| active | boolean | true/false (default: true) |
| in_stock | boolean | Chỉ lấy còn hàng |
| per_page | int | Số lượng/trang |

### PUT `/products/variants/{id}`
Cập nhật variant

**Body (raw JSON):**
```json
{
    "variant_id": "TSHIRT-BLK-M",
    "sku": "SKU-001-NEW",
    "style": "Classic",
    "color": "Black",
    "size": "M",
    "stock": 150,
    "active": true,
    "weight": 200,
    "supplier_price": 6.99
}
```

### PUT `/products/variants/{variantId}/pricing`
Cập nhật giá variant

**Body (raw JSON):**
```json
{
    "prices": [
        {"tier_id": 0, "type": "base_cost", "price": 8.99},
        {"tier_id": 0, "type": "front", "price": 2.50},
        {"tier_id": 1, "type": "base_cost", "price": 7.99}
    ]
}
```

### GET `/products/variants/{variantId}`
Chi tiết variant

### GET `/products/with-variants`
Products kèm variants

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| search | string | Tìm theo name, brand, style |
| style | string | Filter theo style |
| brand | string | Filter theo brand |
| status | string | "1"/"true" = active |
| sort_by | string | created_at, name, brand, style |
| sort_order | string | asc/desc |
| per_page | int | Số lượng/trang |

### GET `/products/colors`
Danh sách colors

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| product_id | int | Filter theo product |

### GET `/products/sizes`
Danh sách sizes

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| product_id | int | Filter theo product |
| color | string | Filter theo color |

### POST `/products/updatestock`
Cập nhật stock

### GET `/products/import/template`
Download import template

### POST `/products/import/preview`
Preview import

### POST `/products/import`
Import CSV

### PUT `/products/{id}`
Cập nhật product

**Body (raw JSON):**
```json
{
    "name": "T-Shirt Classic Updated",
    "style": "Classic V2",
    "status": true,
    "mockup": "https://example.com/mockup-new.jpg",
    "brand": "Brand Name",
    "warehouse_name": "Warehouse A"
}
```

### GET `/products/{id}`
Chi tiết product

---

## 📊 Stock Management

### GET `/stock/summary`
Tổng quan stock

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| product_id | int | ID product |

### GET `/stock/filter-options`
Filter options (styles, colors, sizes)

### GET `/stock`
Danh sách stock

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| variant_id | string | Filter theo variant_id |
| sku | string | Filter theo sku |
| style | string | Filter theo style |
| color | string | Filter theo color |
| size | string | Filter theo size |
| stock_level | string | low/out/normal |
| active_status | string | active/inactive |

### PUT `/stock/variants/{id}`
Cập nhật stock variant

**Body (raw JSON):**
```json
{
    "sku": "SKU-NEW",
    "style": "Classic",
    "stock": 100,
    "active": true,
    "reason": "Nhập hàng mới"
}
```

### GET `/stock/variants/{id}/history`
Lịch sử stock variant (20 records gần nhất)

### POST `/stock/bulk-update`
Cập nhật hàng loạt

**Body (raw JSON):**
```json
{
    "variant_ids": [1, 2, 3],
    "action": "add_stock",
    "stock_value": 50,
    "reason": "Nhập hàng từ nhà cung cấp"
}
```
action: `activate`, `deactivate`, `add_stock`, `subtract_stock`, `set_stock`

### POST `/stock/imports`
Import stock

**Body (form-data):**
| Field | Type | Description |
|-------|------|-------------|
| file | file | File CSV |

### GET `/stock/exports`
Export stock

**Query params:** (same as GET `/stock`)

---

## 📈 Dashboard

### GET `/dashboard/statistics`
Thống kê dashboard

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| time_range | int | Số ngày (default: 30) |

---

## 📝 Stock Audit Logs

### GET `/stock/audit-logs`
Danh sách audit logs

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang (default: 20) |
| page | int | Trang |
| variant_id | string | Filter theo variant_id |
| action | string | increase/decrease/adjust/map/restore/manual |
| user_id | int | Filter theo user |
| style | string | Filter theo style |
| color | string | Filter theo color |
| size | string | Filter theo size |
| order_id | int | Filter theo order |
| date_from | date | Từ ngày |
| date_to | date | Đến ngày |

### GET `/stock/audit-logs/filter-options`
Filter options

### GET `/stock/audit-logs/check-variant`
Check variant productions

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| variant_id | string | Variant ID (required) |

---

## 💰 Transactions/Wallet

### GET `/transactions`
Danh sách transactions

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang |
| page | int | Trang |
| seller_id | int | Filter theo seller |
| date_from | date | Từ ngày |
| date_to | date | Đến ngày |
| type | string | Payment/Refund/Deposit |
| status | string | Status |
| search | string | Tìm kiếm |
| sort_by | string | Sắp xếp theo |
| sort_order | string | asc/desc |

### POST `/transactions/add-fund`
Nạp tiền

**Body (raw JSON):**
```json
{
    "type": "Deposit",
    "amount": 100.50,
    "note": "Nạp tiền qua PayPal",
    "transaction_id": "TXN-123456789"
}
```
type: `Payment`, `Refund`, `Deposit`

### GET `/transactions/export`
Export transactions

**Query params:** (same as GET `/transactions` - trừ pagination)

### GET `/transactions/sellers`
Danh sách sellers cho filter

---

## 🎫 Support Tickets

### GET `/tickets`
Danh sách tickets

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| per_page | int | Số lượng/trang |
| page | int | Trang |
| status | int | 0=Open, 1=Closed |
| ticket_id | string | Tìm theo ticket_id |
| order_id | int | Filter theo order |
| subject | string | Tìm theo subject |
| seller_id | int | Filter theo seller |
| support_id | int | Filter theo support user |
| sort_by | string | Sắp xếp theo |
| sort_order | string | asc/desc |

### POST `/tickets`
Tạo ticket

**Body (form-data):**
| Field | Type | Description |
|-------|------|-------------|
| order_id | int | ID đơn hàng (required) |
| subject | string | Tiêu đề (required) |
| message | string | Nội dung (required) |
| file | file | File đính kèm (jpg,jpeg,png,gif,pdf - max 10MB) |

### GET `/tickets/sellers`
Danh sách sellers cho filter

### GET `/tickets/supports`
Danh sách supports cho filter

### GET `/tickets/{id}`
Chi tiết ticket

### PUT `/tickets/{id}/status` (admin only)
Cập nhật status

**Body (raw JSON):**
```json
{
    "status": 1
}
```
status: 0=Open, 1=Closed

### POST `/tickets/{id}/messages`
Gửi message

**Body (form-data):**
| Field | Type | Description |
|-------|------|-------------|
| message | string | Nội dung (required nếu không có file) |
| file | file | File đính kèm (jpg,jpeg,png,gif,pdf - max 10MB) |

---

## 🏷️ Buy Label

### POST `/buy-label/single`
Mua label đơn lẻ

**Body (raw JSON):**
```json
{
    "order_id": 123
}
```

### POST `/buy-label/batch`
Mua label hàng loạt

**Body (raw JSON):**
```json
{
    "order_ids": [123, 124, 125]
}
```

### POST `/buy-label/check-eligible`
Kiểm tra đơn đủ điều kiện

**Body (raw JSON):**
```json
{
    "order_ids": [123, 124, 125]
}
```

---

## 🎯 Tiers

### GET `/tiers`
Danh sách tiers với extra fees và refund fees

### GET `/tiers/options`
Tier options cho dropdown

### POST `/tiers`
Tạo tier

**Body (raw JSON):**
```json
{
    "tier_selection": 0
}
```
tier_selection: 0=Silver, 1=Gold, 2=Platinum, 3=Diamond

### PUT `/tiers/{id}`
Cập nhật tier

**Body (raw JSON):**
```json
{
    "name": "Silver Plus"
}
```

### DELETE `/tiers/{id}`
Xóa tier

---

### Extra Fees

### POST `/tiers/{tierId}/extra-fee`
Thêm extra fee

**Body (raw JSON):**
```json
{
    "min_stitch": 0,
    "max_stitch": 5000,
    "amount": 0.50
}
```

### PUT `/tiers/{tierId}/extra-fee/{id}`
Cập nhật extra fee

**Body (raw JSON):**
```json
{
    "min_stitch": 0,
    "max_stitch": 6000,
    "amount": 0.75
}
```

### DELETE `/tiers/{tierId}/extra-fee/{id}`
Xóa extra fee

---

### Refund Fees

### POST `/tiers/{tierId}/refund-fee`
Thêm refund fee

**Body (raw JSON):**
```json
{
    "stitch": 5000,
    "amount": 2.00
}
```

### PUT `/tiers/{tierId}/refund-fee/{id}`
Cập nhật refund fee

**Body (raw JSON):**
```json
{
    "stitch": 6000,
    "amount": 2.50
}
```

### DELETE `/tiers/{tierId}/refund-fee/{id}`
Xóa refund fee

---

## 📡 Broadcasting

### POST `/broadcasting/auth`
Auth cho broadcasting (realtime)

---

## 📋 Response Format

Tất cả API trả về format:
```json
{
    "code": 200,
    "status": true,
    "message": "Success message",
    "data": { ... }
}
```

Error format:
```json
{
    "code": 400,
    "status": false,
    "message": "Error message",
    "errors": { ... }
}
```

## 🔑 Authentication

Headers:
```
Authorization: Bearer <jwt_token>
Content-Type: application/json
```
