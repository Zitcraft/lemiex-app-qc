# API Documentation

Base URL: `/api`

---

## 🔐 Auth

| Method | Endpoint | Middleware | Description |
|--------|----------|------------|-------------|
| POST | `/auth/login` | - | Đăng nhập |
| POST | `/auth/logout` | - | Đăng xuất |
| GET | `/auth/me` | jwt.auth | Lấy thông tin user hiện tại |

---

## 👥 Users (admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users` | Tạo user mới |
| GET | `/users` | Danh sách users |
| GET | `/users/{id}` | Chi tiết user |
| PUT | `/users/{id}` | Cập nhật user |
| DELETE | `/users/{id}` | Xóa user |

---

## 📦 Orders

| Method | Endpoint | Middleware | Description |
|--------|----------|------------|-------------|
| POST | `/update-label` | - | Cập nhật label (webhook) |
| GET | `/orders` | jwt.auth | Danh sách đơn hàng |
| POST | `/orders/create` | jwt.auth, rate.limit, seller | Tạo đơn hàng |
| PUT | `/orders/update` | jwt.auth | Cập nhật đơn hàng |
| GET | `/orders/fulfill-statuses` | jwt.auth | Danh sách fulfill statuses |
| PUT | `/orders/change-fulfill-status` | jwt.auth, staff | Đổi fulfill status |
| PUT | `/orders/change-status-items` | jwt.auth | Đổi status items |
| PUT | `/orders/qc-reject` | jwt.auth | QC reject item |
| POST | `/orders/post-label` | jwt.auth | Post label |
| GET | `/orders/update-label` | jwt.auth | Cập nhật label |
| GET | `/orders/track/{orderId}` | jwt.auth | Tracking đơn hàng |
| GET | `/orders/{id}` | jwt.auth | Chi tiết đơn hàng |
| GET | `/orders/{id}/timeline` | jwt.auth | Timeline đơn hàng |
| GET | `/orders/{id}/qr-codes` | jwt.auth | QR codes đơn hàng |
| PUT | `/orders/remake/file` | jwt.auth | Remake file |
| PUT | `/orders/remake/qr` | jwt.auth | Remake QR |
| GET | `/proxy/shipping-label` | - | Proxy shipping label (tránh CORS) |

---

## 🏪 Stores

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stores` | Danh sách stores |
| GET | `/stores/list` | Danh sách stores (dropdown) |
| GET | `/stores/users` | Danh sách users của stores |
| POST | `/stores` | Tạo store |
| PUT | `/stores/{id}` | Cập nhật store |
| GET | `/stores/{id}` | Chi tiết store |

---

## 🛍️ Products

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/products` | Danh sách products |
| POST | `/products` | Tạo product |
| GET | `/products/filter-options` | Filter options |
| GET | `/products/metadata` | Metadata |
| GET | `/products/variants` | Danh sách variants |
| PUT | `/products/variants/{id}` | Cập nhật variant |
| PUT | `/products/variants/{variantId}/pricing` | Cập nhật giá variant |
| GET | `/products/variants/{variantId}` | Chi tiết variant |
| GET | `/products/with-variants` | Products kèm variants |
| GET | `/products/colors` | Danh sách colors |
| GET | `/products/sizes` | Danh sách sizes |
| POST | `/products/updatestock` | Cập nhật stock |
| GET | `/products/import/template` | Download import template |
| POST | `/products/import/preview` | Preview import |
| POST | `/products/import` | Import CSV |
| PUT | `/products/{id}` | Cập nhật product |
| GET | `/products/{id}` | Chi tiết product |

---

## 📊 Stock Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stock/summary` | Tổng quan stock |
| GET | `/stock/filter-options` | Filter options |
| GET | `/stock` | Danh sách stock |
| PUT | `/stock/variants/{id}` | Cập nhật stock variant |
| GET | `/stock/variants/{id}/history` | Lịch sử stock variant |
| POST | `/stock/bulk-update` | Cập nhật hàng loạt |
| POST | `/stock/imports` | Import stock |
| GET | `/stock/exports` | Export stock |

---

## 📈 Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard/statistics` | Thống kê dashboard |

---

## 📝 Stock Audit Logs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stock/audit-logs` | Danh sách audit logs |
| GET | `/stock/audit-logs/filter-options` | Filter options |
| GET | `/stock/audit-logs/check-variant` | Check variant productions |

---

## 💰 Transactions/Wallet

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/transactions` | Danh sách transactions |
| POST | `/transactions/add-fund` | Nạp tiền |
| GET | `/transactions/export` | Export transactions |
| GET | `/transactions/sellers` | Danh sách sellers |

---

## 🎫 Support Tickets

| Method | Endpoint | Middleware | Description |
|--------|----------|------------|-------------|
| GET | `/tickets` | jwt.auth | Danh sách tickets |
| POST | `/tickets` | jwt.auth | Tạo ticket |
| GET | `/tickets/sellers` | jwt.auth | Danh sách sellers |
| GET | `/tickets/supports` | jwt.auth | Danh sách supports |
| GET | `/tickets/{id}` | jwt.auth | Chi tiết ticket |
| PUT | `/tickets/{id}/status` | jwt.auth, admin | Cập nhật status |
| POST | `/tickets/{id}/messages` | jwt.auth | Gửi message |

---

## 🏷️ Buy Label

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/buy-label/single` | Mua label đơn lẻ |
| POST | `/buy-label/batch` | Mua label hàng loạt |
| POST | `/buy-label/check-eligible` | Kiểm tra đơn đủ điều kiện |

---

## 🎯 Tiers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tiers` | Danh sách tiers |
| GET | `/tiers/options` | Tier options (dropdown) |
| POST | `/tiers` | Tạo tier |
| PUT | `/tiers/{id}` | Cập nhật tier |
| DELETE | `/tiers/{id}` | Xóa tier |

### Extra Fees

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tiers/{tierId}/extra-fee` | Thêm extra fee |
| PUT | `/tiers/{tierId}/extra-fee/{id}` | Cập nhật extra fee |
| DELETE | `/tiers/{tierId}/extra-fee/{id}` | Xóa extra fee |

### Refund Fees

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/tiers/{tierId}/refund-fee` | Thêm refund fee |
| PUT | `/tiers/{tierId}/refund-fee/{id}` | Cập nhật refund fee |
| DELETE | `/tiers/{tierId}/refund-fee/{id}` | Xóa refund fee |

---

## 📡 Broadcasting

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/broadcasting/auth` | Auth cho broadcasting (realtime) |
