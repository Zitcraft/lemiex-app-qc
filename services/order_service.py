"""
Order Service - Handle order-related operations.
"""

import logging
from typing import Optional, List, Callable

from models import Order, FulfillStatus
from core import APIClient

logger = logging.getLogger(__name__)


class OrderService:
    """Service for order operations."""
    
    def __init__(self, api_client: APIClient):
        """
        Initialize order service.
        
        Args:
            api_client: API client instance
        """
        self._api_client = api_client
        
        # Cache for recently fetched orders
        self._order_cache: dict = {}
        
        # Callbacks
        self.on_order_loaded: Optional[Callable[[Order], None]] = None
        self.on_status_updated: Optional[Callable[[Order], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
    
    def get_order(self, order_id: str, use_cache: bool = False) -> Optional[Order]:
        """
        Fetch order by ID using /orders/track/{id} endpoint.
        
        Args:
            order_id: Order ID
            use_cache: Whether to use cached order if available
            
        Returns:
            Order object or None if not found
        """
        # Check cache first
        if use_cache and order_id in self._order_cache:
            return self._order_cache[order_id]
        
        try:
            # Use /orders/track/{id} endpoint for full order data
            response = self._api_client.get(f"/orders/track/{order_id}")
            
            # Handle new response structure: { success, data: { order, items, ... } }
            data = response.get("data", response)
            
            # Merge order info with items
            order_info = data.get("order", data)
            items_data = data.get("items", [])
            
            # Create combined data for Order.from_dict
            order_data = {
                **order_info,
                "items": items_data,
                # Map customer to seller
                "seller": data.get("customer", order_info.get("customer", {})),
            }
            
            order = Order.from_dict(order_data)
            
            # Cache the order
            self._order_cache[order_id] = order
            
            logger.info(f"Order loaded: #{order.id} (ref: {order.ref_id})")
            
            if self.on_order_loaded:
                self.on_order_loaded(order)
            
            return order
            
        except Exception as e:
            error_msg = f"Lỗi tải đơn hàng: {e}"
            logger.error(error_msg)
            
            if self.on_error:
                self.on_error(error_msg)
            
            return None
    
    def update_fulfill_status(
        self,
        order_id: str,
        new_status: FulfillStatus
    ) -> bool:
        """
        Update order fulfill status.
        
        Args:
            order_id: Order ID
            new_status: New fulfill status
            
        Returns:
            True if successful
        """
        try:
            response = self._api_client.put(
                "/orders/change-fulfill-status",
                json_data={
                    "order_id": order_id,
                    "fulfill_status": new_status.value
                }
            )
            
            logger.info(f"Order {order_id} status updated to {new_status.value}")
            
            # Update cache
            if order_id in self._order_cache:
                self._order_cache[order_id].status = new_status
                
                if self.on_status_updated:
                    self.on_status_updated(self._order_cache[order_id])
            
            return True
            
        except Exception as e:
            error_msg = f"Lỗi cập nhật trạng thái: {e}"
            logger.error(error_msg)
            
            if self.on_error:
                self.on_error(error_msg)
            
            return False
    
    def attach_video(self, order_id: str, video_url: str) -> bool:
        """
        Attach video URL to order.
        
        Args:
            order_id: Order ID
            video_url: Video URL (from B2 upload)
            
        Returns:
            True if successful
        """
        try:
            response = self._api_client.post(
                f"/orders/{order_id}/videos",
                json_data={
                    "video_url": video_url
                }
            )
            
            logger.info(f"Video attached to order {order_id}")
            
            # Update cache
            if order_id in self._order_cache:
                self._order_cache[order_id].video_url = video_url
            
            return True
            
        except Exception as e:
            error_msg = f"Lỗi gắn video: {e}"
            logger.error(error_msg)
            
            if self.on_error:
                self.on_error(error_msg)
            
            return False
    
    def clear_cache(self) -> None:
        """Clear the order cache."""
        self._order_cache.clear()
    
    def get_cached_order(self, order_id: str) -> Optional[Order]:
        """Get order from cache only."""
        return self._order_cache.get(order_id)
