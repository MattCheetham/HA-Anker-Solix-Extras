"""Immutable measurements shared by Extras entities."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryPower:
    """Signed power readings from one Modbus response, in watts."""

    ac_power: int
    battery_power: int

    @property
    def heating_power(self) -> int:
        """Estimate heating from the power difference during AC absorption."""
        if self.ac_power >= 0:
            return 0
        return max(self.battery_power - self.ac_power, 0)


@dataclass(frozen=True)
class BackupReserve:
    """The battery's reported reserve settings and supported controls."""

    enabled: bool
    switch_supported: bool
    percentage: int | None


@dataclass(frozen=True)
class BatteryMeasurements:
    """Fresh readings; None means that measurement failed this update."""

    temperature: float | None
    power: BatteryPower | None
    state_of_health: int | None
    backup_reserve: BackupReserve | None = None
