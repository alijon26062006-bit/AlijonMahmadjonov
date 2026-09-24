from __future__ import annotations

from ..config import Config
from .base import (
    KIND_TITLES,
    KINDS,
    ProductData,
    Supplier,
    SupplierError,
    SupplierOrder,
    SupplierRejected,
    SupplierUnavailable,
)


def make_supplier(config: Config) -> Supplier:
    if config.supplier == "fazer":
        from .fazer import FazerSupplier

        return FazerSupplier(config.fazer_api_key, config.fazer_base_url)
    if config.supplier == "mock":
        from .mock import MockSupplier

        return MockSupplier()
    raise ValueError(f"DONATIX_SUPPLIER: неизвестный поставщик {config.supplier!r} (fazer или mock)")


__all__ = [
    "KIND_TITLES",
    "KINDS",
    "ProductData",
    "Supplier",
    "SupplierError",
    "SupplierOrder",
    "SupplierRejected",
    "SupplierUnavailable",
    "make_supplier",
]
