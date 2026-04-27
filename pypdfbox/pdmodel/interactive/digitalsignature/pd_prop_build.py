from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName

from .pd_prop_build_data_dict import PDPropBuildDataDict

_FILTER: COSName = COSName.get_pdf_name("Filter")
_PUB_SEC: COSName = COSName.get_pdf_name("PubSec")
_APP: COSName = COSName.get_pdf_name("App")


class PDPropBuild:
    """Signature build properties dictionary as specified in the Adobe
    PDF Signature Build Dictionary Specification. Mirrors PDFBox
    ``PDPropBuild``.

    Provides the typed sub-dictionary accessors for ``/Filter``, ``/PubSec``,
    and ``/App`` as :class:`PDPropBuildDataDict` instances.
    """

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
        else:
            self._dict = dictionary
        # The specification claims to use direct objects.
        self._dict.set_direct(True)

    # ---------- COS object access ----------

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> PDPropBuildDataDict | None:
        """Build data dictionary for the signature handler that was used to
        create the parent signature.
        """
        v = self._dict.get_dictionary_object(_FILTER)
        if isinstance(v, COSDictionary):
            return PDPropBuildDataDict(v)
        return None

    def set_pd_prop_build_filter(self, filter_dict: PDPropBuildDataDict | None) -> None:
        """Set the build data dictionary for the signature handler. Optional
        but highly recommended for signatures.
        """
        if filter_dict is None:
            self._dict.remove_item(_FILTER)
            return
        self._dict.set_item(_FILTER, filter_dict.get_cos_object())

    # ---------- /PubSec ----------

    def get_pub_sec(self) -> PDPropBuildDataDict | None:
        """Build data dictionary for the PubSec software module that was
        used to create the parent signature.
        """
        v = self._dict.get_dictionary_object(_PUB_SEC)
        if isinstance(v, COSDictionary):
            return PDPropBuildDataDict(v)
        return None

    def set_pd_prop_build_pub_sec(self, pub_sec: PDPropBuildDataDict | None) -> None:
        """Set the build data dictionary for the PubSec software module."""
        if pub_sec is None:
            self._dict.remove_item(_PUB_SEC)
            return
        self._dict.set_item(_PUB_SEC, pub_sec.get_cos_object())

    # ---------- /App ----------

    def get_app(self) -> PDPropBuildDataDict | None:
        """Build data dictionary for the viewing application software
        module that was used to create the parent signature.
        """
        v = self._dict.get_dictionary_object(_APP)
        if isinstance(v, COSDictionary):
            return PDPropBuildDataDict(v)
        return None

    def set_pd_prop_build_app(self, app: PDPropBuildDataDict | None) -> None:
        """Set the build data dictionary for the viewing application
        software module.
        """
        if app is None:
            self._dict.remove_item(_APP)
            return
        self._dict.set_item(_APP, app.get_cos_object())


__all__ = ["PDPropBuild"]
