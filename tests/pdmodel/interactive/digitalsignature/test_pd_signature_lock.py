from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignatureLock

# ---------------------------------------------------------------------------
# presence predicates
# ---------------------------------------------------------------------------


def test_has_predicates_default_false() -> None:
    lock = PDSignatureLock()
    assert lock.has_action() is False
    assert lock.has_fields() is False
    assert lock.has_p() is False


def test_has_action_true_after_set() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_ALL)
    assert lock.has_action() is True
    lock.set_action(None)
    assert lock.has_action() is False


def test_has_fields_true_after_set() -> None:
    lock = PDSignatureLock()
    lock.set_fields(["a", "b"])
    assert lock.has_fields() is True
    lock.set_fields(None)
    assert lock.has_fields() is False


def test_has_fields_true_for_empty_list() -> None:
    """An empty array is still a present /Fields entry — the key-only
    predicate must return ``True`` even when ``get_fields`` returns ``[]``.
    """
    lock = PDSignatureLock()
    lock.set_fields([])
    assert lock.has_fields() is True
    assert lock.get_fields() == []


def test_has_p_true_after_set() -> None:
    lock = PDSignatureLock()
    lock.set_p(PDSignatureLock.P_NO_CHANGES)
    assert lock.has_p() is True
    lock.set_p(None)
    assert lock.has_p() is False


# ---------------------------------------------------------------------------
# /Action value predicates
# ---------------------------------------------------------------------------


def test_action_predicates_all_false_when_absent() -> None:
    lock = PDSignatureLock()
    assert lock.is_lock_all() is False
    assert lock.is_lock_include() is False
    assert lock.is_lock_exclude() is False


def test_is_lock_all_only_true_for_action_all() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_ALL)
    assert lock.is_lock_all() is True
    assert lock.is_lock_include() is False
    assert lock.is_lock_exclude() is False


def test_is_lock_include_only_true_for_action_include() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    assert lock.is_lock_all() is False
    assert lock.is_lock_include() is True
    assert lock.is_lock_exclude() is False


def test_is_lock_exclude_only_true_for_action_exclude() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_EXCLUDE)
    assert lock.is_lock_all() is False
    assert lock.is_lock_include() is False
    assert lock.is_lock_exclude() is True


def test_action_predicates_partition_spec_values() -> None:
    """For each spec /Action value, exactly one predicate must report
    ``True`` — this guards against future drift between the constants and
    the predicate implementations.
    """
    lock = PDSignatureLock()
    cases = (
        (PDSignatureLock.ACTION_ALL, "is_lock_all"),
        (PDSignatureLock.ACTION_INCLUDE, "is_lock_include"),
        (PDSignatureLock.ACTION_EXCLUDE, "is_lock_exclude"),
    )
    names = [name for _, name in cases]
    for action, expected in cases:
        lock.set_action(action)
        for name in names:
            actual = getattr(lock, name)()
            assert actual is (name == expected), (
                f"action={action}: {name} expected {name == expected}, got {actual}"
            )


# ---------------------------------------------------------------------------
# /P value predicates
# ---------------------------------------------------------------------------


def test_p_predicates_all_false_when_absent() -> None:
    lock = PDSignatureLock()
    assert lock.is_no_changes() is False
    assert lock.is_allow_form_fill() is False
    assert lock.is_allow_form_fill_and_annotations() is False


def test_p_predicates_partition_spec_values() -> None:
    lock = PDSignatureLock()
    cases = (
        (PDSignatureLock.P_NO_CHANGES, "is_no_changes"),
        (PDSignatureLock.P_ALLOW_FORM_FILL, "is_allow_form_fill"),
        (
            PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS,
            "is_allow_form_fill_and_annotations",
        ),
    )
    names = [name for _, name in cases]
    for p, expected in cases:
        lock.set_p(p)
        for name in names:
            actual = getattr(lock, name)()
            assert actual is (name == expected), (
                f"/P={p}: {name} expected {name == expected}, got {actual}"
            )


def test_p_predicates_false_for_out_of_spec_value() -> None:
    """An unexpected /P value (e.g. ``0`` or ``99`` from a malformed PDF)
    must not be reported as any of the spec levels.
    """
    lock = PDSignatureLock()
    lock.set_p(0)
    assert lock.is_no_changes() is False
    assert lock.is_allow_form_fill() is False
    assert lock.is_allow_form_fill_and_annotations() is False
    lock.set_p(99)
    assert lock.is_no_changes() is False
    assert lock.is_allow_form_fill() is False
    assert lock.is_allow_form_fill_and_annotations() is False


# ---------------------------------------------------------------------------
# __str__ / __repr__
# ---------------------------------------------------------------------------


def test_str_empty_dict_is_marked_empty() -> None:
    """A bare lock dict (only ``/Type /SigFieldLock``) must summarize as
    ``<empty>`` — the type marker isn't user-supplied data.
    """
    lock = PDSignatureLock()
    assert str(lock) == "PDSignatureLock(<empty>)"
    assert repr(lock) == str(lock)


def test_str_lists_action_when_set() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    assert "action=Include" in str(lock)


def test_str_includes_fields_count() -> None:
    """``/Fields`` is summarized by *count* not contents — the names
    themselves can be long and noisy in debug output."""
    lock = PDSignatureLock()
    lock.set_fields(["sig1", "sig2", "sig3"])
    assert "fields=3" in str(lock)


def test_str_includes_p_with_label() -> None:
    lock = PDSignatureLock()
    lock.set_p(PDSignatureLock.P_NO_CHANGES)
    assert "p=1 (no_changes)" in str(lock)
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL)
    assert "p=2 (allow_form_fill)" in str(lock)
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL_AND_ANNOTATIONS)
    assert "p=3 (allow_form_fill_and_annotations)" in str(lock)


def test_str_unknown_p_falls_back_to_int_label() -> None:
    """Out-of-spec /P values must surface as raw integers in the label
    position — useful for spotting malformed PDFs in logs.
    """
    cos = COSDictionary()
    cos.set_int("P", 99)
    lock = PDSignatureLock(cos)
    s = str(lock)
    assert "p=99 (99)" in s


def test_str_full_dict_lists_fields_in_order() -> None:
    lock = PDSignatureLock()
    lock.set_action(PDSignatureLock.ACTION_INCLUDE)
    lock.set_fields(["a", "b"])
    lock.set_p(PDSignatureLock.P_ALLOW_FORM_FILL)
    s = str(lock)
    # action first, then fields count, then /P
    assert s == "PDSignatureLock(action=Include, fields=2, p=2 (allow_form_fill))"
