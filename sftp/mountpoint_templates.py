from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, List, Optional, Tuple

from .glob import SAFE_NAME_RGX


@dataclass(frozen=True)
class MountpointRecord:
    """Resolved configured SFTP mountpoint before physical reconciliation."""

    record_id: str
    label: str
    path: str
    enabled: bool
    rw: bool
    my: bool
    source: str
    template: Optional[str] = None


def _safe_name(value: object) -> bool:
    return isinstance(value, str) and bool(SAFE_NAME_RGX.match(value))


def _bool_field(
    row: Dict,
    field: str,
    default: bool,
    context: str,
    errors: List[str],
) -> bool:
    if field not in row:
        return default
    value = row[field]
    if not isinstance(value, bool):
        errors.append(f"{context}: '{field}' must be a boolean.")
        return default
    return value


def resolve_mountpoint_records(
    config: Dict,
    user_data: Dict,
) -> Tuple[List[MountpointRecord], List[str]]:
    """Resolve local and template mountpoints for one SFTP user.

    Local mountpoints keep the legacy defaults: missing ``enabled`` means
    enabled, missing ``rw`` means read-write and missing ``my`` means owned by
    the SFTP user. Template mountpoints are fail-safe by default: disabled,
    read-only and without source ownership takeover.

    The returned records include disabled entries so callers can render them.
    Physical Apply should use only records where ``enabled`` is true.
    """
    records: List[MountpointRecord] = []
    errors: List[str] = []
    seen_labels: Dict[str, str] = {}
    seen_template_ids: Dict[str, str] = {}

    def append_record(record: MountpointRecord, context: str) -> None:
        previous = seen_labels.get(record.label)
        if previous is not None:
            errors.append(
                f"Mountpoint label conflict '{record.label}': {previous} and {context}."
            )
            return
        seen_labels[record.label] = context
        records.append(record)

    mounts = user_data.get("sftpmounts", {})
    if not isinstance(mounts, dict):
        errors.append("Local 'sftpmounts' must be an object.")
        mounts = {}

    points_set = user_data.get("pointsSet", {})
    if not isinstance(points_set, dict):
        errors.append("Local 'pointsSet' must be an object.")
        points_set = {}

    for label, path in mounts.items():
        context = f"local mountpoint {label!r}"
        if not _safe_name(label):
            errors.append(f"{context}: invalid mountpoint label.")
            continue
        if not isinstance(path, str) or not os.path.isabs(path):
            errors.append(f"{context}: path must be an absolute string.")
            continue

        settings = points_set.get(label, {})
        if settings is None:
            settings = {}
        if not isinstance(settings, dict):
            errors.append(f"{context}: pointsSet entry must be an object.")
            settings = {}

        append_record(
            MountpointRecord(
                record_id=f"local:{label}",
                label=label,
                path=path,
                enabled=_bool_field(settings, "enabled", True, context, errors),
                rw=_bool_field(settings, "rw", True, context, errors),
                my=_bool_field(settings, "my", True, context, errors),
                source="local",
            ),
            context,
        )

    templates = config.get("mountpointTemplates", {})
    if templates is None:
        templates = {}
    if not isinstance(templates, dict):
        errors.append("Root 'mountpointTemplates' must be an object.")
        templates = {}

    assigned = user_data.get("mountTemplates", [])
    if assigned is None:
        assigned = []
    if not isinstance(assigned, list):
        errors.append("User 'mountTemplates' must be an array.")
        assigned = []

    template_points = user_data.get("templatePoints", {})
    if template_points is None:
        template_points = {}
    if not isinstance(template_points, dict):
        errors.append("User 'templatePoints' must be an object.")
        template_points = {}

    for template_name in assigned:
        if not _safe_name(template_name):
            errors.append(f"Invalid assigned mountpoint template name: {template_name!r}.")
            continue
        template = templates.get(template_name)
        if not isinstance(template, dict):
            errors.append(f"Assigned mountpoint template '{template_name}' does not exist.")
            continue
        template_mounts = template.get("mounts", {})
        if not isinstance(template_mounts, dict):
            errors.append(f"Template '{template_name}' field 'mounts' must be an object.")
            continue

        for mount_id, row in template_mounts.items():
            context = f"template '{template_name}' mount {mount_id!r}"
            if not _safe_name(mount_id):
                errors.append(f"{context}: invalid stable mountpoint ID.")
                continue
            previous_template = seen_template_ids.get(mount_id)
            if previous_template is not None:
                errors.append(
                    f"Template mountpoint ID conflict '{mount_id}': "
                    f"'{previous_template}' and '{template_name}'."
                )
                continue
            seen_template_ids[mount_id] = template_name

            if not isinstance(row, dict):
                errors.append(f"{context}: mountpoint definition must be an object.")
                continue
            label = row.get("label")
            path = row.get("path")
            if not _safe_name(label):
                errors.append(f"{context}: invalid mountpoint label.")
                continue
            if not isinstance(path, str) or not os.path.isabs(path):
                errors.append(f"{context}: path must be an absolute string.")
                continue

            settings = template_points.get(mount_id, {})
            if settings is None:
                settings = {}
            if not isinstance(settings, dict):
                errors.append(f"{context}: templatePoints entry must be an object.")
                settings = {}

            append_record(
                MountpointRecord(
                    record_id=mount_id,
                    label=label,
                    path=path,
                    enabled=_bool_field(settings, "enabled", False, context, errors),
                    rw=_bool_field(settings, "rw", False, context, errors),
                    my=False,
                    source="template",
                    template=template_name,
                ),
                context,
            )

    return records, errors


def effective_mountpoint_records(records: List[MountpointRecord]) -> List[MountpointRecord]:
    """Return only mountpoints that should exist in the active SFTP jail."""
    return [record for record in records if record.enabled]
