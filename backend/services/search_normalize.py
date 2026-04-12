def plain_query_value(value: str | None) -> str:
    """
    Trim and remove '*' characters so we send literal search text to Orthanc / C-FIND.
    Universal match still uses '*' only when the user leaves the field empty.
    """
    if not value:
        return ""
    return value.strip().replace("*", "").strip()


def normalize_modalities_in_study(value) -> str:
    """
    Return a single string for API/JSON (DICOM-style backslash-separated CS values).

    pydicom C-FIND identifiers often expose ModalitiesInStudy as MultiValue; str()
    becomes a Python list repr like "['CT', 'MR']", which breaks clients. Orthanc
    may return a JSON list or a plain string.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(x).strip() for x in value if str(x).strip()]
        return "\\".join(parts)
    if isinstance(value, bytes):
        s = value.decode(errors="replace").strip()
    elif isinstance(value, str):
        s = value.strip()
    else:
        s = str(value).strip()
    if not s:
        return ""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        parts: list[str] = []
        for part in inner.split(","):
            p = part.strip().strip("'\"")
            if p:
                parts.append(p)
        return "\\".join(parts) if parts else s
    return s


def patient_name_for_find(value: str | None) -> str:
    """
    Build a PatientName value for C-FIND / Orthanc /tools/find.

    Unstructured input (no '^') is turned into a substring match so one word can
    match either family or given name inside DICOM PN (e.g. DOE^JOHN).

    If the user enters explicit DICOM structure with '^', keep prefix-style
    matching without adding wildcards (same as plain_query_value).
    """
    if not value:
        return ""
    raw = value.strip()
    if not raw:
        return ""
    if "^" in raw:
        return plain_query_value(value)
    core = plain_query_value(value)
    if not core:
        return ""
    tokens = core.split()
    return "*" + "*".join(tokens) + "*"
