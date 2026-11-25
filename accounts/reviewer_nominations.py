"""Parse and validate reviewer nomination CSV files."""

from collections import Counter, defaultdict

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


HEADERS = {
    "participant_name": "participantname",
    "participant_email": "participantemail",
    "rater_name": "ratername",
    "rater_email": "rateremail",
    "rater_group": "ratergroup",
    "source": "source",
}

GROUPS = {
    "self": "self",
    "manager": "manager",
    "supervisor": "manager",
    "line manager": "manager",
    "peer": "peer",
    "direct report": "direct_report",
    "direct reports": "direct_report",
    "directreport": "direct_report",
}


def _normal(value):
    return "".join(character for character in value.lower() if character.isalnum())


def parse_nomination_csv(raw, read_table):
    """Return a read-only preview of a reviewer nomination CSV."""
    headers, rows = read_table(raw)
    normalized_headers = [_normal(header) for header in headers]
    indexes = {}

    for field, expected in HEADERS.items():
        indexes[field] = next(
            (
                index
                for index, header in enumerate(normalized_headers)
                if header == expected
            ),
            None,
        )

    required = (
        "participant_name",
        "participant_email",
        "rater_name",
        "rater_email",
        "rater_group",
    )
    missing = [
        field.replace("_", " ").title()
        for field in required
        if indexes[field] is None
    ]

    preview = {
        "errors": [],
        "warnings": [],
        "participants": [],
        "stats": {
            "rows": 0,
            "participants": 0,
            "assignments": 0,
            "existing_raters": 0,
            "new_raters": 0,
            "duplicates": 0,
            "self": 0,
            "manager": 0,
            "peer": 0,
            "direct_report": 0,
        },
        "rater_emails": set(),
    }

    if missing:
        preview["errors"].append(
            "Missing required columns: " + ", ".join(missing)
        )
        return preview

    def cell(row, field):
        index = indexes[field]
        return row[index].strip() if index is not None and index < len(row) else ""

    assignments = []
    seen = set()
    groups_by_pair = defaultdict(set)
    participant_names = {}
    participant_order = []

    for line_number, row in enumerate(rows, start=2):
        participant_name = cell(row, "participant_name")
        participant_email = cell(row, "participant_email").lower()
        rater_name = cell(row, "rater_name")
        rater_email = cell(row, "rater_email").lower()
        raw_group = cell(row, "rater_group")
        source = cell(row, "source")

        # Exported blank Peer rows are templates, not assignments.
        if not rater_name and not rater_email:
            continue

        preview["stats"]["rows"] += 1
        line_errors = []

        if not participant_name:
            line_errors.append("participant name is empty")
        try:
            validate_email(participant_email)
        except ValidationError:
            line_errors.append(
                f'participant email "{participant_email}" is invalid'
            )

        if not rater_name:
            line_errors.append("rater name is empty")
        try:
            validate_email(rater_email)
        except ValidationError:
            line_errors.append(f'rater email "{rater_email}" is invalid')

        normalized_group = " ".join(
            raw_group.strip().lower().replace("_", " ").split()
        )
        category = GROUPS.get(normalized_group)
        if category is None:
            line_errors.append(
                f'rater group "{raw_group}" must be Self, Manager, '
                "Supervisor, Peer, or Direct Report"
            )

        if line_errors:
            preview["errors"].append(
                f"Line {line_number}: " + "; ".join(line_errors) + "."
            )
            continue

        if participant_email not in participant_names:
            participant_names[participant_email] = participant_name
            participant_order.append(participant_email)
        elif participant_names[participant_email] != participant_name:
            preview["warnings"].append(
                f'Participant {participant_email} has more than one name: '
                f'"{participant_names[participant_email]}" and '
                f'"{participant_name}".'
            )

        key = (participant_email, rater_email, category)
        if key in seen:
            preview["stats"]["duplicates"] += 1
            preview["warnings"].append(
                f"Line {line_number}: duplicate assignment for "
                f"{rater_email} as {raw_group} for {participant_email}."
            )
            continue
        seen.add(key)

        pair = (participant_email, rater_email)
        groups_by_pair[pair].add(category)

        assignments.append({
            "line": line_number,
            "participant_name": participant_name,
            "participant_email": participant_email,
            "rater_name": rater_name,
            "rater_email": rater_email,
            "category": category,
            "group": {
                "self": "Self",
                "manager": "Manager",
                "peer": "Peer",
                "direct_report": "Direct Report",
            }[category],
            "source": source,
        })
        preview["stats"][category] += 1
        preview["rater_emails"].add(rater_email)

    for (participant_email, rater_email), categories in groups_by_pair.items():
        if len(categories) > 1:
            labels = ", ".join(sorted(categories))
            preview["warnings"].append(
                f"{rater_email} appears in multiple groups for "
                f"{participant_email}: {labels}."
            )

    by_participant = defaultdict(list)
    for assignment in assignments:
        by_participant[assignment["participant_email"]].append(assignment)

    for participant_email in participant_order:
        participant_assignments = by_participant[participant_email]
        categories = Counter(
            assignment["category"] for assignment in participant_assignments
        )
        preview["participants"].append({
            "name": participant_names[participant_email],
            "email": participant_email,
            "assignments": participant_assignments,
            "counts": {
                "self": categories["self"],
                "manager": categories["manager"],
                "peer": categories["peer"],
                "direct_report": categories["direct_report"],
            },
        })

        if categories["self"] == 0:
            preview["warnings"].append(
                f"{participant_email} has no Self assignment."
            )
        elif categories["self"] > 1:
            preview["warnings"].append(
                f"{participant_email} has more than one Self assignment."
            )

    preview["stats"]["participants"] = len(preview["participants"])
    preview["stats"]["assignments"] = len(assignments)
    return preview
