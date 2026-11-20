"""Сетевой слой hackmeskay.

Реальные сокеты используются ТОЛЬКО для транспорта комнат и мессенджера.
Все «атаки», сканирования и IP «Серверных империй» — симуляция в empire.py.
"""

from .identity import MessengerID, load_or_create_identity
from .room import NetworkManager

__all__ = ["MessengerID", "load_or_create_identity", "NetworkManager"]
