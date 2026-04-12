def plain_query_value(value: str | None) -> str:
    """
    Trim and remove '*' characters so we send literal search text to Orthanc / C-FIND.
    Universal match still uses '*' only when the user leaves the field empty.
    """
    if not value:
        return ""
    return value.strip().replace("*", "").strip()


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
