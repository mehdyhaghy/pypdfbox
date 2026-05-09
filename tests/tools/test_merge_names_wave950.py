from __future__ import annotations

import tests.tools.test_merge_names as merge_names
from pypdfbox.cos import COSDictionary, COSString


def test_wave950_named_destination_link_action_branch_is_exercised(
    monkeypatch,
    tmp_path,
) -> None:
    def fake_build(path, **kwargs):  # noqa: ANN001
        path.write_bytes(b"%PDF-1.4\n%%EOF\n")
        return path

    class _FakePage:
        def __init__(self) -> None:
            action = COSDictionary()
            action.set_item(
                merge_names._D,
                merge_names.COSName.get_pdf_name("not-a-string-after-rewrite"),
            )
            link = COSDictionary()
            link.set_item(merge_names._DEST, COSString("go#2"))
            link.set_item(merge_names._A, action)
            annots = merge_names.COSArray()
            annots.add(link)
            self._dict = COSDictionary()
            self._dict.set_item(merge_names._ANNOTS, annots)

        def get_cos_object(self) -> COSDictionary:
            return self._dict

    class _FakeMergedDoc:
        def __init__(self) -> None:
            self._pages = [_FakePage(), _FakePage()]

        def __enter__(self) -> _FakeMergedDoc:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def get_pages(self) -> list[_FakePage]:
            return self._pages

        def get_document_catalog(self) -> object:
            return object()

    monkeypatch.setattr(merge_names, "_build_pdf_with_names", fake_build)
    monkeypatch.setattr(merge_names.cli, "run_cli", lambda _argv: 0)
    monkeypatch.setattr(
        merge_names.PDDocument,
        "load",
        staticmethod(lambda _path: _FakeMergedDoc()),
    )
    monkeypatch.setattr(
        merge_names,
        "_name_tree_entries",
        lambda doc, _category: (
            doc.get_document_catalog(),
            {
                "go#2": merge_names.COSArray(
                    [
                        doc.get_pages()[1].get_cos_object(),
                        merge_names.COSName.get_pdf_name("Fit"),
                    ]
                )
            },
        )[1],
    )

    merge_names.test_merge_rewrites_named_destination_links_when_name_is_suffixed(
        tmp_path
    )
