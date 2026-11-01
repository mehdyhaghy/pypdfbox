from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .open_mode import OpenMode
    from .pd_action import PDAction
    from .pd_action_embedded_go_to import PDActionEmbeddedGoTo
    from .pd_action_factory import PDActionFactory
    from .pd_action_go_to import PDActionGoTo
    from .pd_action_go_to_3d_view import PDActionGoTo3DView
    from .pd_action_go_to_dp import PDActionGoToDp
    from .pd_action_hide import PDActionHide
    from .pd_action_import_data import PDActionImportData
    from .pd_action_java_script import PDActionJavaScript
    from .pd_action_launch import PDActionLaunch
    from .pd_action_movie import PDActionMovie
    from .pd_action_named import PDActionNamed
    from .pd_action_remote_go_to import PDActionRemoteGoTo
    from .pd_action_rendition import PDActionRendition
    from .pd_action_reset_form import PDActionResetForm
    from .pd_action_rich_media_execute import PDActionRichMediaExecute
    from .pd_action_set_ocg_state import PDActionSetOCGState
    from .pd_action_sound import PDActionSound
    from .pd_action_submit_form import PDActionSubmitForm
    from .pd_action_thread import PDActionThread
    from .pd_action_transition import PDActionTransition
    from .pd_action_unknown import PDActionUnknown
    from .pd_action_uri import PDActionURI
    from .pd_additional_actions import PDAdditionalActions
    from .pd_annotation_additional_actions import PDAnnotationAdditionalActions
    from .pd_document_catalog_additional_actions import PDDocumentCatalogAdditionalActions
    from .pd_form_field_additional_actions import PDFormFieldAdditionalActions
    from .pd_page_additional_actions import PDPageAdditionalActions
    from .pd_target_directory import PDTargetDirectory
    from .pd_uri_dictionary import PDURIDictionary
    from .pd_windows_launch_params import PDWindowsLaunchParams

__getattr__, __dir__ = _attach(
    __name__,
    {
        "OpenMode": ".open_mode",
        "PDAction": ".pd_action",
        "PDActionEmbeddedGoTo": ".pd_action_embedded_go_to",
        "PDActionFactory": ".pd_action_factory",
        "PDActionGoTo": ".pd_action_go_to",
        "PDActionGoTo3DView": ".pd_action_go_to_3d_view",
        "PDActionGoToDp": ".pd_action_go_to_dp",
        "PDActionHide": ".pd_action_hide",
        "PDActionImportData": ".pd_action_import_data",
        "PDActionJavaScript": ".pd_action_java_script",
        "PDActionLaunch": ".pd_action_launch",
        "PDActionMovie": ".pd_action_movie",
        "PDActionNamed": ".pd_action_named",
        "PDActionRemoteGoTo": ".pd_action_remote_go_to",
        "PDActionRendition": ".pd_action_rendition",
        "PDActionResetForm": ".pd_action_reset_form",
        "PDActionRichMediaExecute": ".pd_action_rich_media_execute",
        "PDActionSetOCGState": ".pd_action_set_ocg_state",
        "PDActionSound": ".pd_action_sound",
        "PDActionSubmitForm": ".pd_action_submit_form",
        "PDActionThread": ".pd_action_thread",
        "PDActionTransition": ".pd_action_transition",
        "PDActionUnknown": ".pd_action_unknown",
        "PDActionURI": ".pd_action_uri",
        "PDAdditionalActions": ".pd_additional_actions",
        "PDAnnotationAdditionalActions": ".pd_annotation_additional_actions",
        "PDDocumentCatalogAdditionalActions": ".pd_document_catalog_additional_actions",
        "PDFormFieldAdditionalActions": ".pd_form_field_additional_actions",
        "PDPageAdditionalActions": ".pd_page_additional_actions",
        "PDTargetDirectory": ".pd_target_directory",
        "PDURIDictionary": ".pd_uri_dictionary",
        "PDWindowsLaunchParams": ".pd_windows_launch_params",
    },
)

__all__ = [
    "OpenMode",
    "PDAction",
    "PDActionEmbeddedGoTo",
    "PDActionFactory",
    "PDActionGoTo",
    "PDActionGoTo3DView",
    "PDActionGoToDp",
    "PDActionHide",
    "PDActionImportData",
    "PDActionJavaScript",
    "PDActionLaunch",
    "PDActionMovie",
    "PDActionNamed",
    "PDActionRemoteGoTo",
    "PDActionRendition",
    "PDActionResetForm",
    "PDActionRichMediaExecute",
    "PDActionSetOCGState",
    "PDActionSound",
    "PDActionSubmitForm",
    "PDActionThread",
    "PDActionTransition",
    "PDActionURI",
    "PDActionUnknown",
    "PDAdditionalActions",
    "PDAnnotationAdditionalActions",
    "PDDocumentCatalogAdditionalActions",
    "PDFormFieldAdditionalActions",
    "PDPageAdditionalActions",
    "PDTargetDirectory",
    "PDURIDictionary",
    "PDWindowsLaunchParams",
]
