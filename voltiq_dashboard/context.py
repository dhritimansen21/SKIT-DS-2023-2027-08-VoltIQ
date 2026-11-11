from dataclasses import dataclass, field
from datetime import datetime
import pandas as pd


@dataclass
class Ctx:
    """Everything a view needs, built once per run in app.py."""
    provider: object
    user: dict
    devices: pd.DataFrame            # devices this user may see
    device_id: str                   # currently selected device
    start: datetime                  # sidebar date range (start of first day)
    end: datetime                    # sidebar date range (end of last day)

    @property
    def is_admin(self) -> bool:
        return self.user["role"] == "administrator"

    @property
    def device_ids(self):
        return list(self.devices["device_id"])
