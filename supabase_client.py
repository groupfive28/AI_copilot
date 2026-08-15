"""
supabase_client.py
-------------------
Writes face verification results to Supabase, which is what your
verification portal reads from.

Configure via environment variables (see config.py):
    SUPABASE_URL
    SUPABASE_KEY               (use the service_role key for server-side writes,
                                 NOT the anon/public key -- this process writes
                                 on behalf of the system, not an end user)
    SUPABASE_RESULTS_TABLE      (default: "face_verification_results")

Expected table shape (create this in Supabase SQL editor, adjust as needed):

    create table face_verification_results (
        id              uuid primary key default gen_random_uuid(),
        director_id     text not null,
        overall_result  text not null,          -- MATCHED | MISMATCH | NEEDS_REVIEW
        best_similarity_score  float,
        documents_checked      jsonb not null,  -- full per-document breakdown
        reasons                jsonb,
        created_at      timestamptz not null default now()
    );

    -- if you want at-most-one-row-per-director (upsert on re-verification):
    create unique index if not exists face_verification_results_director_id_key
        on face_verification_results (director_id);
"""

import logging
from typing import Optional

import config

logger = logging.getLogger("face_verification.supabase")

_client = None


def _get_client():
    """
    Lazily creates the Supabase client. Requires the `supabase` package
    (pip install supabase). Kept lazy so importing this module doesn't
    hard-fail in environments where Supabase isn't configured yet (e.g.
    while running purely local tests).
    """
    global _client
    if _client is not None:
        return _client

    if not config.SUPABASE_URL or not config.SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set (as environment variables) "
            "before writing verification results to Supabase."
        )

    from supabase import create_client
    _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    logger.info("Supabase client initialised (table=%s)", config.SUPABASE_RESULTS_TABLE)
    return _client


def write_verification_result(result: dict):
    """
    Upserts the aggregated verification result for a director into Supabase.
    `result` is the dict produced by decision_engine.aggregate_multi_document_decision
    (see verification_service.py for the exact shape written).
    """
    client = _get_client()

    row = {
        "director_id": result["director_id"],
        "overall_result": result["overall_result"],
        "best_similarity_score": result.get("best_similarity_score"),
        "documents_checked": result.get("documents_checked", []),
        "reasons": result.get("reasons", []),
    }

    response = (
        client.table(config.SUPABASE_RESULTS_TABLE)
        .upsert(row, on_conflict="director_id")
        .execute()
    )
    logger.info("Wrote verification result to Supabase for director_id=%s -> %s",
                result["director_id"], result["overall_result"])
    return response
