"""PubChem connector: search compounds and retrieve hazard and safety data.

Uses the public PUG-REST and PUG-View web services of the U.S. National
Library of Medicine (no key required; please keep below 5 requests/second).
GHS data in PubChem aggregate several sources (e.g. ECHA C&L notifications);
the share of notifications reporting each hazard statement is returned so the
user can decide which codes to accept.

    Kim, S. et al. (2019) PUG-View: programmatic access to chemical annotations
    integrated in PubChem. J. Cheminform. 11, 56.
"""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field

from ..hazards import H_STATEMENTS
from .http import NotFound, get_json

BASE = "https://pubchem.ncbi.nlm.nih.gov/rest"
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")
H_RE = re.compile(r"\b(H\d{3})[A-Za-z]*\b(?:\s*\((\d+(?:\.\d+)?)%\))?")


@dataclass
class Candidate:
    cid: int
    name: str
    formula: str = ""
    molecular_weight: float | None = None
    cas: str = ""

    @property
    def url(self) -> str:
        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{self.cid}"


@dataclass
class SafetyData:
    cid: int
    name: str
    cas: str = ""
    h_codes: dict[str, float | None] = field(default_factory=dict)  # code -> max share of notifications (%)
    signal_word: str = ""
    flash_point_c: float | None = None
    lel_vol: float | None = None
    uel_vol: float | None = None
    oel_ppm: float | None = None
    raw: dict[str, list[str]] = field(default_factory=dict)  # source strings for review

    def accepted_codes(self, min_share: float = 0.0) -> list[str]:
        """Hazard statements reported by at least ``min_share`` % of notifications."""
        return sorted(c for c, s in self.h_codes.items() if s is None or s >= min_share)

    def to_substance(self, role: str = "intermediate", min_share: float = 0.0) -> dict:
        d = {"name": self.name.lower(), "role": role, "h_codes": self.accepted_codes(min_share)}
        if self.cas:
            d["cas"] = self.cas
        for k in ("flash_point_c", "lel_vol", "uel_vol", "oel_ppm"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
def autocomplete(text: str, limit: int = 10) -> list[str]:
    """Name suggestions for a partial query."""
    q = urllib.parse.quote(text.strip())
    data = get_json(f"{BASE}/autocomplete/compound/{q}/json?limit={limit}")
    return parse_autocomplete(data)


def parse_autocomplete(data: dict) -> list[str]:
    return list(data.get("dictionary_terms", {}).get("compound", []))


def search(query: str, max_results: int = 8) -> list[Candidate]:
    """Find compounds by name, synonym or CAS number."""
    q = urllib.parse.quote(query.strip())
    try:
        data = get_json(f"{BASE}/pug/compound/name/{q}/cids/JSON")
    except NotFound:
        return []
    cids = data.get("IdentifierList", {}).get("CID", [])[:max_results]
    if not cids:
        return []
    props = get_json(f"{BASE}/pug/compound/cid/{','.join(map(str, cids))}"
                     "/property/Title,MolecularFormula,MolecularWeight/JSON")
    cands = parse_properties(props)
    for c in cands:
        try:
            c.cas = cas_number(c.cid)
        except Exception:
            c.cas = ""
    return cands


def parse_properties(data: dict) -> list[Candidate]:
    out = []
    for p in data.get("PropertyTable", {}).get("Properties", []):
        mw = p.get("MolecularWeight")
        out.append(Candidate(cid=int(p["CID"]), name=p.get("Title", str(p["CID"])),
                             formula=p.get("MolecularFormula", ""),
                             molecular_weight=float(mw) if mw not in (None, "") else None))
    return out


def cas_number(cid: int) -> str:
    data = get_json(f"{BASE}/pug/compound/cid/{cid}/synonyms/JSON")
    return parse_cas(data)


def parse_cas(data: dict) -> str:
    for info in data.get("InformationList", {}).get("Information", []):
        for s in info.get("Synonym", []):
            if CAS_RE.match(s):
                return s
    return ""


# ---------------------------------------------------------------------------
# PUG-View annotations
# ---------------------------------------------------------------------------
def _strings(section_json: dict, name_filter=None) -> list[str]:
    """All text strings in a PUG-View record (optionally only from Information
    blocks whose Name contains ``name_filter``)."""
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            if "Information" in node:
                for info in node["Information"]:
                    if name_filter and name_filter.lower() not in str(info.get("Name", "")).lower():
                        continue
                    for swm in info.get("Value", {}).get("StringWithMarkup", []):
                        if swm.get("String"):
                            out.append(swm["String"])
            for v in node.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(section_json)
    return out


def _heading(cid: int, heading: str) -> dict | None:
    h = urllib.parse.quote_plus(heading)
    try:
        return get_json(f"{BASE}/pug_view/data/compound/{cid}/JSON?heading={h}")
    except NotFound:
        return None


def parse_ghs(data: dict | None) -> tuple[dict[str, float | None], str, list[str]]:
    """Return ({H-code: max share %}, signal word, raw statements) from a GHS Classification record."""
    if not data:
        return {}, "", []
    statements = _strings(data, "Hazard Statements")
    codes: dict[str, float | None] = {}
    for s in statements:
        for code, share in H_RE.findall(s):
            if code not in H_STATEMENTS:
                continue
            val = float(share) if share else None
            prev = codes.get(code)
            codes[code] = val if prev is None else (prev if val is None else max(prev, val))
    signals = _strings(data, "Signal")
    signal = "Danger" if any("Danger" in s for s in signals) else ("Warning" if signals else "")
    return codes, signal, statements


def _to_c(value: float, unit: str) -> float:
    return round((value - 32) * 5 / 9, 1) if unit.upper().startswith("F") else value


def parse_flash_point(strings: list[str]) -> float | None:
    """First temperature in °C (or converted from °F)."""
    pat = re.compile(r"(-?\d+(?:\.\d+)?)\s*°?\s*([CF])\b")
    for s in strings:
        m = re.search(r"(-?\d+(?:\.\d+)?)\s*°\s*C\b", s)
        if m:
            return float(m.group(1))
        m = pat.search(s)
        if m:
            return _to_c(float(m.group(1)), m.group(2))
    return None


def parse_explosive_limits(strings: list[str]) -> tuple[float | None, float | None]:
    text = " ; ".join(strings)
    lo = re.search(r"(?:lower|LEL|LFL)[^0-9]{0,40}?(\d+(?:\.\d+)?)\s*%", text, re.I)
    hi = re.search(r"(?:upper|UEL|UFL)[^0-9]{0,40}?(\d+(?:\.\d+)?)\s*%", text, re.I)
    if lo and hi:
        return float(lo.group(1)), float(hi.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*%?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*%", text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return min(a, b), max(a, b)
    return (float(lo.group(1)) if lo else None), (float(hi.group(1)) if hi else None)


def parse_oel_ppm(strings: list[str]) -> float | None:
    """Lowest 8-h TWA value in ppm mentioned (indicative only)."""
    vals = []
    for s in strings:
        if re.search(r"STEL|ceiling|IDLH", s, re.I) and not re.search(r"TWA", s, re.I):
            continue
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*ppm", s, re.I):
            vals.append(float(m.group(1)))
    return min(vals) if vals else None


def safety_data(cid: int, name: str | None = None) -> SafetyData:
    """Collect GHS hazard statements and key physico-chemical safety data for one compound."""
    if name is None:
        props = parse_properties(get_json(f"{BASE}/pug/compound/cid/{cid}/property/Title/JSON"))
        name = props[0].name if props else str(cid)
    sd = SafetyData(cid=cid, name=name)
    try:
        sd.cas = cas_number(cid)
    except Exception:
        pass
    codes, signal, statements = parse_ghs(_heading(cid, "GHS Classification"))
    sd.h_codes, sd.signal_word = codes, signal
    sd.raw["GHS hazard statements"] = statements
    fp = _heading(cid, "Flash Point")
    if fp:
        sd.raw["Flash point"] = _strings(fp)
        sd.flash_point_c = parse_flash_point(sd.raw["Flash point"])
    el = _heading(cid, "Explosive Limits and Potential")
    if el:
        sd.raw["Explosive limits"] = _strings(el)
        sd.lel_vol, sd.uel_vol = parse_explosive_limits(sd.raw["Explosive limits"])
    for heading in ("Threshold Limit Values (TLV)", "Permissible Exposure Limit (PEL)"):
        tl = _heading(cid, heading)
        if tl:
            sd.raw[heading] = _strings(tl)
            sd.oel_ppm = parse_oel_ppm(sd.raw[heading])
            if sd.oel_ppm is not None:
                break
    return sd
