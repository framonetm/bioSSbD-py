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


class MethodMismatchError(ConnectorError):
    """All impacts are zero although the inventory has emissions.

    Typical cause: the LCIA methods were imported for a different elementary-flow list
    than the database (e.g. generic openLCA LCIA methods in a USLCI/FEDEFL database), so
    no characterisation factor matches a flow by UUID and every score is silently 0.
    """


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
            if out and all(r.amount == 0.0 for r in out):
                n = _nonzero_flows(result)
                if n:
                    raise MethodMismatchError(
                        f"All {len(out)} impact results are 0 although the inventory has {n} non-zero "
                        "elementary flows: the LCIA method's characterisation factors do not match the "
                        "database's elementary flows. Import the LCIA method package made for this "
                        "database (same flow list), e.g. from openLCA Nexus or the Federal LCA Commons "
                        "for USLCI; see docs/openlca_setup.md.")
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
        except MethodMismatchError:
            raise  # a product system would give the same zeros
        except ConnectorError:
            ps = self.create_product_system(process_id)
            return self.calculate(ps.id, method_id, amount=1.0)

    def method_coverage(self, process_id: str, method_id: str, top: int = 5) -> dict:
        """How many non-zero inventory flows of 1 unit of a process have a factor in the method.

        Factors are matched by flow UUID, as openLCA does. Returns ``matched``, ``flows`` and
        ``largest_unmatched``: the ``top`` largest flows (by |amount|) without any factor, as
        (name, compartment, amount). A low ``matched`` with CO2 or methane among the unmatched
        means the method and the database use different elementary-flow lists.
        """
        o = self.o
        try:
            m = self.client.get(o.ImpactMethod, method_id)
            ids = set()
            for ic in (getattr(m, "impact_categories", None) or []):
                cat = self.client.get(o.ImpactCategory, ic.id)
                ids |= {cf.flow.id for cf in (getattr(cat, "impact_factors", None) or [])}
            setup = o.CalculationSetup(target=o.Ref(ref_type=o.RefType.Process, id=process_id),
                                       impact_method=o.Ref(ref_type=o.RefType.ImpactMethod, id=method_id),
                                       amount=1.0)
            result = self.client.calculate(setup)
        except Exception as e:
            raise ConnectorError(f"openLCA coverage check failed: {e}") from e
        try:
            if hasattr(result, "wait_until_ready"):
                result.wait_until_ready()
            flows = [v for v in (result.get_total_flows() or []) if float(v.amount or 0.0) != 0.0]
        finally:
            if hasattr(result, "dispose"):
                result.dispose()
        unmatched = sorted((v for v in flows if v.envi_flow.flow.id not in ids),
                           key=lambda v: -abs(float(v.amount)))
        return {"matched": len(flows) - len(unmatched), "flows": len(flows),
                "largest_unmatched": [(v.envi_flow.flow.name or "", getattr(v.envi_flow.flow, "category", "") or "",
                                       float(v.amount)) for v in unmatched[:top]]}


def _nonzero_flows(result) -> int:
    """Number of non-zero elementary flows in a result (0 if the result cannot report them)."""
    try:
        flows = result.get_total_flows() or []
    except Exception:
        return 0
    return sum(1 for v in flows if float(getattr(v, "amount", 0.0) or 0.0) != 0.0)


def to_indicators(results: list[ImpactResult], source: str, prefix: str = "") -> dict[str, DataPoint]:
    return {f"{prefix}{r.category}": DataPoint(value=r.amount, unit=r.unit, source=source, evidence="modelled")
            for r in results}
