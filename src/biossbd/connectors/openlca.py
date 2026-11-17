"""openLCA connector (openLCA 2.x desktop application via its IPC server).

Requirements:
- openLCA 2 (free, MPL-2.0) with a database open, e.g. one of the free
  databases from openLCA Nexus (USLCI, Agribalyse, ELCD, ...) or a licensed one;
- the IPC server started in openLCA: Tools > Developer tools > IPC Server (port 8080);
- ``pip install olca-ipc`` (MPL-2.0; installs olca-schema).
"""
from __future__ import annotations

from dataclasses import dataclass

from ..dataquality import DataPoint
from .http import ConnectorError


@dataclass
class Item:
    id: str
    name: str
    category: str = ""


@dataclass
class ImpactResult:
    category: str
    unit: str
    amount: float


def installed() -> bool:
    try:
        import olca_ipc  # noqa: F401
        import olca_schema  # noqa: F401
        return True
    except ImportError:
        return False


class OpenLCA:
    """Thin wrapper around ``olca_ipc.Client``; ``client`` may be injected for testing."""

    def __init__(self, port: int = 8080, client=None, schema=None):
        if client is None:
            if not installed():
                raise ConnectorError("olca-ipc is not installed: pip install olca-ipc")
            import olca_ipc as ipc
            import olca_schema as o
            client, schema = ipc.Client(port), o
        self.client = client
        self.o = schema
        self.port = port

    # -- browsing -----------------------------------------------------------
    def _descriptors(self, cls) -> list[Item]:
        try:
            refs = self.client.get_descriptors(cls) or []
        except Exception as e:
            raise ConnectorError(f"openLCA IPC server not reachable on port {self.port}: {e}") from e
        return sorted((Item(r.id, r.name or "", getattr(r, "category", "") or "") for r in refs),
                      key=lambda i: i.name.lower())

    def ping(self) -> bool:
        try:
            self._descriptors(self.o.ImpactMethod)
            return True
        except ConnectorError:
            return False

    def product_systems(self) -> list[Item]:
        return self._descriptors(self.o.ProductSystem)

    def impact_methods(self) -> list[Item]:
        return self._descriptors(self.o.ImpactMethod)

    def processes(self, query: str = "", limit: int = 50) -> list[Item]:
        q = query.lower().strip()
        items = [p for p in self._descriptors(self.o.Process) if q in p.name.lower()]
        return items[:limit]

    def create_product_system(self, process_id: str) -> Item:
        """Create (and store in the open database) a product system linked with default providers."""
        o = self.o
        try:
            ref = self.client.create_product_system(o.Ref(ref_type=o.RefType.Process, id=process_id))
        except Exception as e:
            raise ConnectorError(f"openLCA could not create the product system: {e}") from e
        if ref is None:
            raise ConnectorError("openLCA could not create the product system")
        return Item(ref.id, ref.name or "")

    def reference(self, process_id: str) -> tuple[str, str]:
        """(reference flow name, unit) of a process, e.g. ("transport, freight, lorry", "t*km")."""
        try:
            p = self.client.get(self.o.Process, process_id)
        except Exception as e:
            raise ConnectorError(f"openLCA could not read process {process_id}: {e}") from e
        for ex in (getattr(p, "exchanges", None) or []):
            if getattr(ex, "is_quantitative_reference", False):
                flow, unit = getattr(ex, "flow", None), getattr(ex, "unit", None)
                return (getattr(flow, "name", "") or ""), (getattr(unit, "name", "") or "")
        return "", ""

    # -- calculation ---------------------------------------------------------
    def calculate(self, system_id: str, method_id: str, amount: float | None = None,
                  target_type: str = "ProductSystem") -> list[ImpactResult]:
        o = self.o
        kw = dict(target=o.Ref(ref_type=getattr(o.RefType, target_type), id=system_id),
                  impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=method_id))
        if amount is not None:
            kw["amount"] = amount
        setup = o.CalculationSetup(**kw)
        try:
            result = self.client.calculate(setup)
        except Exception as e:
            raise ConnectorError(f"openLCA calculation failed: {e}") from e
        try:
            if hasattr(result, "wait_until_ready"):
                result.wait_until_ready()
            out = []
            for iv in result.get_total_impacts():
                cat = iv.impact_category
                out.append(ImpactResult(category=cat.name or "", unit=getattr(cat, "ref_unit", "") or "",
                                        amount=float(iv.amount or 0.0)))
            return out
        finally:
            if hasattr(result, "dispose"):
                result.dispose()

    def unit_impacts(self, process_id: str, method_id: str) -> list[ImpactResult]:
        """Impacts of one unit of a process's reference flow, with its supply chain.

        openLCA 2 can calculate a process directly (providers linked on the fly), which
        leaves the database unchanged. If the server refuses a process target, a product
        system is created from the process (stored in the database) and calculated instead.
        """
        try:
            return self.calculate(process_id, method_id, amount=1.0, target_type="Process")
        except ConnectorError:
            ps = self.create_product_system(process_id)
            return self.calculate(ps.id, method_id, amount=1.0)


def to_indicators(results: list[ImpactResult], source: str, prefix: str = "") -> dict[str, DataPoint]:
    return {f"{prefix}{r.category}": DataPoint(value=r.amount, unit=r.unit, source=source, evidence="modelled")
            for r in results}
