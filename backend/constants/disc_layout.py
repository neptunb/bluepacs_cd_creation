"""Directory names for retrieve workspaces, ZIP roots, and on-disc layouts.

ZIP (``burn._zip_study_tree``): members under ``WORKSPACE_STUDY_ZIP_SUBDIR/<StudyInstanceUID>/…``.

Default retrieve + K-PACS ISO: ``work_dir/WORKSPACE_DICOM_SUBDIR/`` is copied to K-PACS
staging as ``DICOM/`` (then interchange / DICOMDIR).

OHIF ISO (``CdBuilderService.build_iso``): ``work_dir/WORKSPACE_DICOM_SUBDIR/`` is renamed or
copied to staging ``OHIF_DISC_IMAGE_SUBDIR/`` (lowercase) for the embedded viewer — not
``STUDY/`` and not a root ``DICOM/`` folder on the OHIF patient disc.

Keep ``frontend/messages/*.json`` strings ``burnPanel.hintZip`` and ``burnPanel.ohifReady``
aligned with these values.
"""

WORKSPACE_DICOM_SUBDIR = "DICOM"
WORKSPACE_STUDY_ZIP_SUBDIR = "STUDY"
OHIF_DISC_IMAGE_SUBDIR = "study"
