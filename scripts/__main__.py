#!/usr/bin/env python3
"""dfc-customer-sync 包入口。

用法：
  python -m dfc_customer_sync --setup
  python -m dfc_customer_sync
  python -m dfc_customer_sync --status
"""

from . import sync_daemon

if __name__ == "__main__":
    sync_daemon.main()
