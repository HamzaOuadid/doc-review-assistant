import pytest

from doc_review.models import Document, FieldSpec


@pytest.fixture
def sample_document() -> Document:
    text = (
        "This Master Services Agreement is entered into as of January 1, 2024 "
        '(the "Effective Date") by and between Acme Corp and Widget Inc. '
        "This Agreement shall be governed by and construed in accordance with "
        "the laws of the State of Delaware, without regard to conflict of laws "
        "principles. Termination for Convenience. Either party may terminate "
        "this Agreement at any time upon thirty (30) days written notice. "
        "Confidential Information means any non-public information disclosed "
        "by either party. Assignment. Neither party may assign this Agreement "
        "without the other party's prior written consent."
    )
    return Document(id="sample_doc", source_text=text)


@pytest.fixture
def date_field() -> FieldSpec:
    return FieldSpec(
        name="effective_date",
        description="effective date",
        guidance="find the date",
        strong_patterns=[r"as of\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})"],
        weak_patterns=[r"Effective Date"],
    )
