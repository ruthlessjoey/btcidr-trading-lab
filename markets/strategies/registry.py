"""markets/strategies/registry.py - the explicit strategy registry (M5).

Rules:
  - registration is explicit: nothing is discovered, imported by name or loaded from a plugin directory;
  - one version per strategy id in a registry. Registering the same id and version again is a DuplicateStrategyError.
    Registering the same id at a different version is a VersionConflictError. Neither replaces the existing entry;
  - lookup requires both id and version. An unknown id is an UnknownStrategyError. A version that is not the registered
    one is a VersionConflictError. There is no fallback to another strategy, another version or a default;
  - describe() returns inspectable plain metadata, so a selection can be recorded and reproduced.
"""
from markets.strategies import contract as C


class StrategyRegistry:
    def __init__(self):
        self._by_id = {}

    def register(self, strategy):
        C.validate_identity(strategy)
        sid = strategy.strategy_id
        if sid in self._by_id:
            existing = self._by_id[sid]
            if existing.version == strategy.version:
                raise C.DuplicateStrategyError(f"strategy {sid!r} version {strategy.version!r} is already registered")
            raise C.VersionConflictError(
                f"strategy {sid!r} is registered at version {existing.version!r}; refusing to register "
                f"{strategy.version!r} alongside it")
        self._by_id[sid] = strategy
        return strategy

    def lookup(self, strategy_id, version):
        if strategy_id not in self._by_id:
            raise C.UnknownStrategyError(f"no strategy named {strategy_id!r}; registered: "
                                         f"{', '.join(self.ids()) or 'none'}")
        existing = self._by_id[strategy_id]
        if version != existing.version:
            raise C.VersionConflictError(
                f"strategy {strategy_id!r} is registered at version {existing.version!r}, not {version!r}")
        return existing

    def ids(self):
        return tuple(sorted(self._by_id))

    def describe(self):
        return [self._by_id[sid].describe() for sid in sorted(self._by_id)]


def default_registry():
    """A fresh registry holding the strategies shipped with M5. Each call builds a new one; nothing is global."""
    from markets.strategies.btc_s1 import BtcS1DailyTrend
    registry = StrategyRegistry()
    registry.register(BtcS1DailyTrend())
    return registry
