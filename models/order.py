"""
Order model - Represents an order from Lemiex system.
Updated to match new API response structure.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any, Dict

from .status import FulfillStatus


@dataclass
class Design:
    """Represents a design for an order item."""
    position: str = ""
    meta_id: int = 0
    pdf_url: str = ""
    dst_url: str = ""
    emb_url: str = ""
    pes_url: str = ""
    json_url: str = ""
    status: int = 0
    qc_status: int = 0
    stitch_count: int = 0
    width_mm: float = 0.0
    height_mm: float = 0.0
    color_count: int = 0
    colors: List[Dict[str, Any]] = field(default_factory=list)
    needle_assignment: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Design":
        """Create Design from dictionary."""
        return cls(
            position=data.get("position", ""),
            meta_id=data.get("meta_id", 0),
            pdf_url=data.get("pdf_url", ""),
            dst_url=data.get("dst_url", ""),
            emb_url=data.get("emb_url") or "",
            pes_url=data.get("pes_url", ""),
            json_url=data.get("json_url", ""),
            status=data.get("status", 0),
            qc_status=data.get("qc_status", 0),
            stitch_count=data.get("stitch_count", 0),
            width_mm=data.get("width_mm", 0.0),
            height_mm=data.get("height_mm", 0.0),
            color_count=data.get("color_count", 0),
            colors=data.get("colors", []),
            needle_assignment=data.get("needle_assignment", {})
        )


@dataclass
class ProductInfo:
    """Represents product variant information."""
    variant_id: str = ""
    product_name: str = ""
    size: str = ""
    color: str = ""
    style: str = ""
    stock: int = 0
    sku: str = ""
    color_image: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductInfo":
        """Create ProductInfo from dictionary."""
        if data is None:
            return cls()
        return cls(
            variant_id=str(data.get("variant_id", "")),
            product_name=data.get("product_name", ""),
            size=data.get("size", ""),
            color=data.get("color", ""),
            style=data.get("style", ""),
            stock=int(data.get("stock", 0)),
            sku=data.get("sku", ""),
            color_image=data.get("color_image", "")
        )


@dataclass
class OrderItem:
    """Represents a single item in an order."""
    id: str
    variant_id: str = ""
    product_name: str = ""
    quantity: int = 1
    status: bool = False
    mockup: str = ""
    mockup_back: str = ""
    designs: List[Design] = field(default_factory=list)
    # New product info fields
    product: Optional["ProductInfo"] = None
    size: str = ""
    color: str = ""
    style: str = ""
    stock: int = 0
    color_image: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderItem":
        """Create OrderItem from dictionary."""
        designs = []
        for design_data in data.get("designs", []):
            designs.append(Design.from_dict(design_data))
        
        # Parse product info (new structure)
        product_data = data.get("product", {})
        product = ProductInfo.from_dict(product_data) if product_data else None
        
        # Get product name from product object or directly
        product_name = ""
        variant_id = ""
        size = ""
        color = ""
        style = ""
        stock = 0
        color_image = ""
        
        if product:
            product_name = product.product_name
            variant_id = product.variant_id
            size = product.size
            color = product.color
            style = product.style
            stock = product.stock
            color_image = product.color_image
        else:
            product_name = data.get("product_name", data.get("name", ""))
            variant_id = str(data.get("variant_id", ""))
        
        return cls(
            id=str(data.get("id", "")),
            variant_id=variant_id,
            product_name=product_name,
            quantity=int(data.get("quantity", 1)),
            status=data.get("status", False),
            mockup=data.get("mockup", ""),
            mockup_back=data.get("mockup_back", ""),
            designs=designs,
            product=product,
            size=size,
            color=color,
            style=style,
            stock=stock,
            color_image=color_image
        )


@dataclass
class ShippingAddress:
    """Represents shipping address."""
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    street1: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShippingAddress":
        """Create ShippingAddress from dictionary."""
        if data is None:
            return cls()
        return cls(
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or "",
            phone=data.get("phone") or "",
            street1=data.get("street1") or "",
            street2=data.get("street2") or "",
            city=data.get("city") or "",
            state=data.get("state") or "",
            zip=data.get("zip") or "",
            country=data.get("country") or ""
        )
    
    def full_name(self) -> str:
        """Get full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p)
    
    def full_address(self) -> str:
        """Get full formatted address."""
        parts = []
        if self.street1:
            parts.append(self.street1)
        if self.street2:
            parts.append(self.street2)
        city_line = ", ".join(p for p in [self.city, self.state, self.zip] if p)
        if city_line:
            parts.append(city_line)
        if self.country:
            parts.append(self.country)
        return "\n".join(parts) if parts else "Không có địa chỉ"


@dataclass
class ShippingInfo:
    """Represents shipping information for an order."""
    method: str = ""
    service: str = ""
    label_url: str = ""
    tracking_id: str = ""
    address: ShippingAddress = field(default_factory=ShippingAddress)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ShippingInfo":
        """Create ShippingInfo from dictionary."""
        if data is None:
            return cls()
        
        address_data = data.get("address", {})
        address = ShippingAddress.from_dict(address_data)
        
        return cls(
            method=data.get("method", ""),
            service=data.get("service", ""),
            label_url=data.get("label_url", ""),
            tracking_id=str(data.get("tracking_id", "")),
            address=address
        )
    
    def full_address(self) -> str:
        """Get full formatted address."""
        return self.address.full_address()


@dataclass
class SellerInfo:
    """Represents seller information."""
    id: int = 0
    username: str = ""
    email: str = ""
    tier: str = ""
    store_name: str = ""
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SellerInfo":
        """Create SellerInfo from dictionary."""
        if data is None:
            return cls()
        return cls(
            id=data.get("id", 0),
            username=data.get("username", ""),
            email=data.get("email", ""),
            tier=data.get("tier", ""),
            store_name=data.get("store_name", "")
        )


@dataclass
class PricingInfo:
    """Represents pricing information."""
    print_cost: float = 0.0
    shipping_cost: float = 0.0
    extra_fee: float = 0.0
    refund_fee: float = 0.0
    priority_fee: float = 0.0
    total_cost: float = 0.0
    profit_margin: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PricingInfo":
        """Create PricingInfo from dictionary."""
        if data is None:
            return cls()
        return cls(
            print_cost=float(data.get("print_cost", 0)),
            shipping_cost=float(data.get("shipping_cost", 0)),
            extra_fee=float(data.get("extra_fee", 0)),
            refund_fee=float(data.get("refund_fee", 0)),
            priority_fee=float(data.get("priority_fee", 0)),
            total_cost=float(data.get("total_cost", 0)),
            profit_margin=float(data.get("profit_margin", 0))
        )


@dataclass
class Order:
    """Represents an order from Lemiex system."""
    id: str
    ref_id: str = ""
    seller_ref: str = ""
    order_stt: str = ""
    order_type: str = ""
    status: FulfillStatus = FulfillStatus.NEW
    fulfill_status: FulfillStatus = FulfillStatus.NEW
    payment_status: str = ""
    processing_status: str = ""
    production_statuses: List[str] = field(default_factory=list)
    priority_level: str = "normal"
    convert_label: str = ""
    note: str = ""
    
    seller: SellerInfo = field(default_factory=SellerInfo)
    shipping: ShippingInfo = field(default_factory=ShippingInfo)
    items: List[OrderItem] = field(default_factory=list)
    pricing: PricingInfo = field(default_factory=PricingInfo)
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    video_url: str = ""
    
    # Extra metadata
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create Order from API response dictionary."""
        # Parse items
        items = []
        items_data = data.get("items", [])
        for item_data in items_data:
            items.append(OrderItem.from_dict(item_data))
        
        # Parse shipping
        shipping_data = data.get("shipping", {})
        shipping = ShippingInfo.from_dict(shipping_data)
        
        # Parse seller
        seller_data = data.get("seller", {})
        seller = SellerInfo.from_dict(seller_data)
        
        # Parse pricing
        pricing_data = data.get("pricing", {})
        pricing = PricingInfo.from_dict(pricing_data)
        
        # Parse status
        status_str = data.get("status", "new")
        status = FulfillStatus.from_string(status_str)
        
        fulfill_status_str = data.get("fulfill_status", status_str)
        fulfill_status = FulfillStatus.from_string(fulfill_status_str)
        
        # Parse dates from timestamps
        timestamps = data.get("timestamps", {})
        created_at = None
        created_str = timestamps.get("created_at", data.get("created_at"))
        if created_str:
            try:
                created_at = datetime.fromisoformat(
                    created_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        updated_at = None
        updated_str = timestamps.get("updated_at", data.get("updated_at"))
        if updated_str:
            try:
                updated_at = datetime.fromisoformat(
                    updated_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        
        return cls(
            id=str(data.get("id", "")),
            ref_id=data.get("ref_id", ""),
            seller_ref=data.get("seller_ref", ""),
            order_stt=data.get("order_stt", ""),
            order_type=data.get("order_type") or "",
            status=status,
            fulfill_status=fulfill_status,
            payment_status=data.get("payment_status", ""),
            processing_status=data.get("processing_status", ""),
            production_statuses=data.get("production_statuses", []),
            priority_level=data.get("priority_level", "normal"),
            convert_label=data.get("convert_label", ""),
            note=data.get("note") or "",
            seller=seller,
            shipping=shipping,
            items=items,
            pricing=pricing,
            created_at=created_at,
            updated_at=updated_at,
            video_url=data.get("video_url", ""),
            raw_data=data
        )
    
    @classmethod
    def from_qr_url(cls, url: str) -> Optional[str]:
        """
        Extract order ID from QR code URL.
        Expected format: https://manage.lemiex.us/orders/{order_id}
        Returns order_id or None if invalid.
        """
        if not url:
            return None
        
        # Handle various URL formats
        import re
        patterns = [
            r"/orders/track/(\d+)",
            r"/order/track/(\d+)",
            r"order_id=(\d+)",
            r"id=(\d+)"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # If URL is just a number, return it
        if url.strip().isdigit():
            return url.strip()
        
        return None
    
    def items_summary(self) -> str:
        """Get a summary of items in the order."""
        if not self.items:
            return "Không có sản phẩm"
        
        summaries = []
        for item in self.items:
            summaries.append(f"{item.product_name} x{item.quantity}")
        
        return "\n".join(summaries)
    
    def total_items_count(self) -> int:
        """Get total count of items."""
        return sum(item.quantity for item in self.items)
    
    def get_status_display(self) -> str:
        """Get display string for current status."""
        return self.fulfill_status.display_name()
    
    def get_seller_display(self) -> str:
        """Get display string for seller."""
        if self.seller.store_name:
            return f"{self.seller.store_name} ({self.seller.tier})"
        return self.seller.username or "N/A"
    
    def get_total_cost_display(self) -> str:
        """Get formatted total cost."""
        return f"${self.pricing.total_cost:.2f}"
