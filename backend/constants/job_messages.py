"""Stable labels for CD build job status messages (i18n keys for the UI).

The API still sends ``message`` in English for logs and non-UI clients.
"""

# Keys — keep in sync with frontend `burnPanel.jobMessages` in messages/*.json
CREATING_STUDY_ZIP = "creating_study_zip"
STUDY_ZIP_READY = "study_zip_ready"
OHIF_ISO_READY_KPACS_FAILED = "ohif_iso_ready_kpacs_failed"
BOTH_ISOS_READY = "both_isos_ready"
ISO_READY_DOWNLOAD_BURN = "iso_ready_download_burn"
RETRIEVING_DICOM_PACS_INITIAL = "retrieving_dicom_pacs_initial"
RETRIEVING_DICOM_PACS_FRACTION = "retrieving_dicom_pacs_fraction"
RETRIEVING_DICOM_PACS_COUNT = "retrieving_dicom_pacs_count"

DEFAULT_MESSAGE_TEXT: dict[str, str] = {
    CREATING_STUDY_ZIP: "Creating ZIP of STUDY folder...",
    STUDY_ZIP_READY: (
        "STUDY folder ZIP is ready — it contains only the retrieved instances "
        "under STUDY/<StudyInstanceUID>/..."
    ),
    OHIF_ISO_READY_KPACS_FAILED: (
        "OHIF ISO is ready below. K-PACS ISO failed — see the message under "
        "the K-PACS download button."
    ),
    BOTH_ISOS_READY: (
        "Both disc images are ready: OHIF viewer ISO and K-PACS layout ISO "
        "(download below)."
    ),
    ISO_READY_DOWNLOAD_BURN: "ISO ready — download it and burn to CD on your PC",
    RETRIEVING_DICOM_PACS_INITIAL: "Retrieving DICOM files from PACS... (0)",
}
