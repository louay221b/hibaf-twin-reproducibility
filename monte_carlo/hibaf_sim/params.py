"""Load and validate literature-derived parameter sets. None is never imputed."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml

TIMING_FIELDS = ("T_HECM_ms", "T_HAdd_ms", "T_hash_ms", "T_AEAD_enc_ms", "T_AEAD_dec_ms")
ROLES = ("sensor", "pond", "station", "dt")
ALLOWED_STATUS = {"LITERATURE_REPORTED", "USER_SUPPLIED_WITH_SOURCE", "TEMPLATE"}
ALLOWED_SEMANTICS = {None, "as_reported_by_source", "full_jacobian_scalar_mult", "kummer_x_only", "unspecified"}


@dataclass(frozen=True)
class ParamSet:
    name: str
    provenance_status: str
    source: Optional[str]
    platform: Optional[str]
    security_label: Optional[str]
    reference_mapped_roles: tuple
    timings: dict = field(default_factory=dict)
    display_name: Optional[str] = None
    hecm_semantics: Optional[str] = None
    notes: Optional[str] = None

    def get(self, fieldname: str, role: str, scenario_roles=()):
        if role not in self.reference_mapped_roles and role not in scenario_roles:
            return None, f"{fieldname}:role_{role}_not_mapped_by_reference_illustration"
        if fieldname == "T_HECM_ms" and self.hecm_semantics == "kummer_x_only":
            return None, "T_HECM_ms:kummer_x_only_not_interchangeable_with_full_group_operation"
        v = self.timings.get(fieldname)
        if v is None:
            return None, f"{fieldname}:null"
        return v, None

    def role_status(self, role: str, scenario_roles=()) -> str:
        if role in self.reference_mapped_roles:
            return "reference_illustration_mapping"
        if role in scenario_roles:
            return "uniform_reference_scenario"
        return "not_covered"


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _validate(raw: dict) -> ParamSet:
    name = raw.get("name")
    if not name:
        raise ValueError("parameter set without a name")
    status = raw.get("provenance_status")
    if status not in ALLOWED_STATUS:
        raise ValueError(f"{name}: provenance_status must be one of {sorted(ALLOWED_STATUS)}")
    timings = {}
    for f in TIMING_FIELDS:
        v = raw.get(f)
        if v is not None:
            v = float(v)
            if not v > 0:
                raise ValueError(f"{name}: {f} must be > 0 or null")
        timings[f] = v
    if any(v is not None for v in timings.values()) and not raw.get("source"):
        raise ValueError(f"{name}: numeric timings require an identified 'source'")
    if status != "TEMPLATE" and not raw.get("source"):
        raise ValueError(f"{name}: non-template sets require a 'source'")
    roles = tuple(raw.get("reference_mapped_roles") or ())
    for r in roles:
        if r not in ROLES:
            raise ValueError(f"{name}: unknown role {r}")
    sem = raw.get("hecm_semantics")
    if sem not in ALLOWED_SEMANTICS:
        raise ValueError(f"{name}: hecm_semantics must be one of {sorted(s for s in ALLOWED_SEMANTICS if s)}")
    return ParamSet(name, status, raw.get("source"), raw.get("platform"),
                    raw.get("security_label"), roles, timings,
                    raw.get("display_name") or name, sem, raw.get("notes"))


def load_param_sets(cfg: dict) -> list:
    sets = [_validate(r) for r in cfg["param_sets"]]
    names = [s.name for s in sets]
    if len(set(names)) != len(names):
        raise ValueError("duplicate parameter-set names")
    return sets
