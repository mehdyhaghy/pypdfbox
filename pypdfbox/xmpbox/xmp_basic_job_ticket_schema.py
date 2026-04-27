from __future__ import annotations

from typing import TYPE_CHECKING

from .xmp_schema import XMPSchema

if TYPE_CHECKING:
    from .xmp_metadata import XMPMetadata


class JobType:
    """
    Lite port of ``org.apache.xmpbox.type.JobType``.

    Upstream JobType is an ``AbstractStructuredType`` with three text fields —
    ``id`` / ``name`` / ``url`` — under the ``stJob`` namespace
    ``http://ns.adobe.com/xap/1.0/sType/Job#``. Cluster #1 has not yet ported
    the ``AbstractStructuredType`` family, so JobType is implemented as a
    minimal value object: it stores the three field strings plus the field
    prefix used when serialising into the parent schema's namespace map.

    The dict-shape representation (returned by :meth:`as_dict`) is what the
    parent schema actually stores in its ``JobRef`` Bag. That keeps storage
    consistent with the ``PDFAExtensionSchema`` extension-list pattern in this
    cluster and gives the parser a stable shape to round-trip later.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/sType/Job#"
    PREFERRED_PREFIX = "stJob"

    ID = "id"
    NAME = "name"
    URL = "url"

    def __init__(
        self,
        metadata: XMPMetadata | None = None,
        field_prefix: str | None = None,
    ) -> None:
        self._metadata = metadata
        self._prefix = field_prefix or self.PREFERRED_PREFIX
        self._id: str | None = None
        self._name: str | None = None
        self._url: str | None = None

    # --- identity ----------------------------------------------------

    def get_namespace(self) -> str:
        return self.NAMESPACE

    def get_prefix(self) -> str | None:
        return self._prefix

    def set_prefix(self, prefix: str | None) -> None:
        self._prefix = prefix or self.PREFERRED_PREFIX

    # --- fields ------------------------------------------------------

    def get_id(self) -> str | None:
        return self._id

    def set_id(self, value: str | None) -> None:
        self._id = value

    def get_name(self) -> str | None:
        return self._name

    def set_name(self, value: str | None) -> None:
        self._name = value

    def get_url(self) -> str | None:
        return self._url

    def set_url(self, value: str | None) -> None:
        self._url = value

    # --- dict round-trip --------------------------------------------

    def as_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self._id is not None:
            out[self.ID] = self._id
        if self._name is not None:
            out[self.NAME] = self._name
        if self._url is not None:
            out[self.URL] = self._url
        return out

    @classmethod
    def from_dict(
        cls,
        data: dict[str, str],
        metadata: XMPMetadata | None = None,
        field_prefix: str | None = None,
    ) -> JobType:
        job = cls(metadata, field_prefix)
        job._id = data.get(cls.ID)
        job._name = data.get(cls.NAME)
        job._url = data.get(cls.URL)
        return job

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JobType):
            return NotImplemented
        return (
            self._id == other._id
            and self._name == other._name
            and self._url == other._url
        )

    def __hash__(self) -> int:
        return hash((self._id, self._name, self._url))

    def __repr__(self) -> str:
        return f"JobType(id={self._id!r}, name={self._name!r}, url={self._url!r})"


class XMPBasicJobTicketSchema(XMPSchema):
    """
    Representation of the XMP Basic Job Ticket schema.

    Ported (subset, read+write path) from
    ``org.apache.xmpbox.schema.XMPBasicJobTicketSchema`` (PDFBox 3.0). The
    schema carries a single Bag property — ``JobRef`` — whose entries are
    :class:`JobType` structures with ``id`` / ``name`` / ``url`` fields. It is
    used by workflow systems to attach references to the job(s) that produced
    the asset described by the surrounding XMP packet.

    Storage shape: cluster #1 stores ``JobRef`` as a list of plain dicts
    (one per job) keyed by upstream's ``id`` / ``name`` / ``url`` field
    names. The :class:`JobType` helper provides typed accessors over that
    dict; :meth:`get_jobs` materialises the list of typed instances on demand.
    """

    NAMESPACE = "http://ns.adobe.com/xap/1.0/bj/"
    PREFERRED_PREFIX = "xmpBJ"

    JOB_REF = "JobRef"

    def __init__(self, metadata: XMPMetadata, own_prefix: str | None = None) -> None:
        super().__init__(metadata, self.NAMESPACE, own_prefix or self.PREFERRED_PREFIX)
        self.add_namespace(JobType.PREFERRED_PREFIX, JobType.NAMESPACE)

    # --- JobRef Bag ---------------------------------------------------

    def _get_job_list(self) -> list[dict[str, str]]:
        existing = self._properties.get(self.JOB_REF)
        if isinstance(existing, list) and all(isinstance(item, dict) for item in existing):
            return existing  # type: ignore[return-value]
        if existing is None:
            new_list: list[dict[str, str]] = []
            self._properties[self.JOB_REF] = new_list
            return new_list
        return []

    def add_job(
        self,
        id: str | None,
        name: str | None,
        url: str | None,
        field_prefix: str | None = None,
    ) -> None:
        """
        Mirror of upstream ``addJob(String id, String name, String url[, String fieldPrefix])``.
        Append a new :class:`JobType` to the ``JobRef`` Bag using the given
        scalar values. ``field_prefix`` lets callers override the default
        ``stJob`` prefix when emitting alongside other Job sub-namespaces;
        upstream uses the first job's prefix as a default to keep all entries
        consistent.
        """
        jobs = self._get_job_list()
        if field_prefix is None and jobs:
            # mirror upstream "use same prefix for all jobs" behavior
            field_prefix = JobType.PREFERRED_PREFIX
        job = JobType(self._metadata, field_prefix)
        job.set_id(id)
        job.set_name(name)
        job.set_url(url)
        self.add_job_type(job)

    def add_job_type(self, job: JobType) -> None:
        """
        Mirror of upstream ``addJob(JobType job)``. Append an already-built
        :class:`JobType` instance to the ``JobRef`` Bag, registering its
        namespace declaration on this schema if not already present.
        """
        prefix = job.get_prefix() or JobType.PREFERRED_PREFIX
        if prefix not in self._namespaces:
            self.add_namespace(prefix, job.get_namespace())
        jobs = self._get_job_list()
        jobs.append(job.as_dict())

    def get_jobs(self) -> list[JobType] | None:
        """
        Mirror of upstream ``getJobs()``. Return a fresh list of :class:`JobType`
        instances reflecting the current ``JobRef`` Bag contents, or ``None``
        when the property is absent. Upstream raises ``BadFieldValueException``
        when the bag contains a non-Job entry; cluster #1 stores entries as
        dicts so that branch is unreachable here.
        """
        existing = self._properties.get(self.JOB_REF)
        if existing is None:
            return None
        if not isinstance(existing, list):
            return []
        out: list[JobType] = []
        for item in existing:
            if isinstance(item, dict):
                out.append(JobType.from_dict(item, self._metadata))
        return out

    def remove_job(self, job: JobType) -> None:
        existing = self._properties.get(self.JOB_REF)
        if not isinstance(existing, list):
            return
        target = job.as_dict()
        try:
            existing.remove(target)
        except ValueError:
            pass

    def clear_jobs(self) -> None:
        self.remove_property(self.JOB_REF)
