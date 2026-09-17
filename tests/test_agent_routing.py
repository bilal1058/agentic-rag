from pathlib import Path


def match_sources_for_query(query: str, all_known_sources: list[str]) -> list[str]:
    query_lower = query.lower()
    matched_sources = []
    for s in all_known_sources:
        stem = Path(s).stem.lower().replace("_", " ").replace("-", " ")
        stem_words = [w for w in stem.split() if len(w) > 3 and w not in {"guide", "reference", "complete", "resume"}]
        if Path(s).name.lower() in query_lower or stem in query_lower:
            matched_sources.append(s)
        elif any(w in query_lower for w in stem_words):
            matched_sources.append(s)
    return matched_sources


def test_source_keyword_matching():
    all_known_sources = [
        "Muhammad_Bilal_Resume.pdf",
        "Arham Tahir.pdf",
        "python_complete_reference_guide.pdf",
    ]

    # Query mentioning Bilal
    matched = match_sources_for_query("tellme some bilal projects", all_known_sources)
    assert matched == ["Muhammad_Bilal_Resume.pdf"]

    # Query mentioning both Bilal and Arham
    matched_both = match_sources_for_query(
        "How to make production ready projects not like demo apps which bilal has and claims them but arham has live apps",
        all_known_sources,
    )
    assert "Muhammad_Bilal_Resume.pdf" in matched_both
    assert "Arham Tahir.pdf" in matched_both

    # Query mentioning python
    matched_py = match_sources_for_query("summarize python guide", all_known_sources)
    assert matched_py == ["python_complete_reference_guide.pdf"]

    # General query
    matched_gen = match_sources_for_query("what are general tips for interviews?", all_known_sources)
    assert matched_gen == []
