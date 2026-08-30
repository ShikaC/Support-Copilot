from collections.abc import Collection, Sequence


def citation_ids_are_valid(
    expected_evidence_ids: Collection[str],
    cited_chunk_ids: Sequence[str],
    retrieved_chunk_ids: Collection[str],
    allowed_chunk_ids: Collection[str],
) -> bool:
    """Validate resolved citation IDs against retrieval and evaluation evidence."""
    expected_ids = set(expected_evidence_ids)
    cited_ids = tuple(cited_chunk_ids)
    cited_id_set = set(cited_ids)
    retrieved_ids = set(retrieved_chunk_ids)
    allowed_ids = set(allowed_chunk_ids)

    return (
        bool(expected_ids & retrieved_ids)
        and bool(cited_ids)
        and len(cited_ids) == len(cited_id_set)
        and cited_id_set <= retrieved_ids
        and cited_id_set <= allowed_ids
        and bool(expected_ids & cited_id_set)
    )
