def plain_query_value(value: str | None) -> str:
    """
    Trim and remove '*' characters so we send literal search text to Orthanc / C-FIND.
    Universal match still uses '*' only when the user leaves the field empty.
    """
    if not value:
        return ""
    return value.strip().replace("*", "").strip()
