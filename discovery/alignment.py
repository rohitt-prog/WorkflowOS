"""
WorkFlowOS Phase 8.2: Local Sequence Alignment & Pattern Matching

Provides deterministic local alignment algorithms for discovering repeated workflow
patterns embedded within longer activity sessions, tolerating:
1. Prefix and suffix noise (unrelated actions before/after workflow)
2. Insertions (unrelated actions between canonical workflow steps)
3. Deletions (missing actions in an otherwise repeated workflow)
4. Transpositions (small adjacent step swaps, e.g. A->B vs B->A)

Uses semi-global dynamic programming (free start and end gaps in target session)
with Damerau-Levenshtein transposition extension.
Pure Python, deterministic, O(m*n), zero external dependencies.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class LocalAlignmentResult:
    """
    Result of aligning pattern P against session sequence S.
    Enhanced in Phase 8.5 with:
    - is_partial_match: indicates partial workflow execution (abandoned/interrupted)
    - matched_pattern_indices: indices in pattern that successfully matched
    - missing_pattern_indices: indices in pattern that were omitted (optional steps)
    - max_consecutive_insertions: peak intermediate noise stretch encountered
    """
    similarity: float
    start_idx: int
    end_idx: int
    aligned_pattern: List[str]
    aligned_target: List[str]
    matches: int
    insertions: int
    deletions: int
    transpositions: int
    is_match: bool
    is_partial_match: bool = False
    matched_pattern_indices: List[int] = field(default_factory=list)
    missing_pattern_indices: List[int] = field(default_factory=list)
    max_consecutive_insertions: int = 0


def compute_longest_common_subsequence(seq_a: List[str], seq_b: List[str]) -> List[str]:
    """
    Computes the Longest Common Subsequence (LCS) between two event sequences.
    Order-preserving.
    """
    m, n = len(seq_a), len(seq_b)
    if m == 0 or n == 0:
        return []

    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq_a[i - 1] == seq_b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # Backtrack to reconstruct LCS
    lcs: List[str] = []
    i, j = m, n
    while i > 0 and j > 0:
        if seq_a[i - 1] == seq_b[j - 1]:
            lcs.append(seq_a[i - 1])
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1

    lcs.reverse()
    return lcs


def local_sequence_alignment(
    pattern: List[str],
    target: List[str],
    similarity_threshold: float = 0.80,
    match_score: float = 2.0,
    mismatch_penalty: float = 1.0,
    gap_penalty: float = 1.0,
    transposition_score: float = 1.8,
    min_coverage: float = 0.75,
    max_consecutive_insertions: int = 3,
) -> LocalAlignmentResult:
    """
    Aligns pattern P (length m) locally against target session S (length n).
    Allows free start and end gaps in S (pattern can appear anywhere within S).
    Penalizes gaps/mismatches within P and the matched window of S.
    Supports adjacent step transpositions (P[i-1]==S[j-2] and P[i-2]==S[j-1]).

    Phase 8.5 enhancements:
    - Bounded noise tolerance: rejects matches if consecutive noise insertions > max_consecutive_insertions
    - Tracks matched and missing pattern step indices (enabling optional-step detection)
    - Distinguishes full/approximate matches from partial support executions

    Returns a LocalAlignmentResult with normalized similarity in [0.0, 1.0].
    """
    m = len(pattern)
    n = len(target)

    # Empty guards
    if m == 0 or n == 0:
        return LocalAlignmentResult(
            similarity=0.0,
            start_idx=0,
            end_idx=0,
            aligned_pattern=[],
            aligned_target=[],
            matches=0,
            insertions=0,
            deletions=0,
            transpositions=0,
            is_match=False,
            is_partial_match=False,
            matched_pattern_indices=[],
            missing_pattern_indices=[],
            max_consecutive_insertions=0,
        )

    # DP table: dp[i][j] = max score aligning pattern[0:i] to target[0:j]
    # start_pos[i][j] tracks the starting index in target for this alignment path
    dp = [[0.0] * (n + 1) for _ in range(m + 1)]
    start_pos = [[0] * (n + 1) for _ in range(m + 1)]

    # Base cases:
    # Row 0: free start gap in target (pattern can start at any j)
    for j in range(n + 1):
        dp[0][j] = 0.0
        start_pos[0][j] = j

    # Col 0: pattern prefix before target is penalized
    for i in range(1, m + 1):
        dp[i][0] = -i * gap_penalty
        start_pos[i][0] = 0

    # Backtracking pointers: 1=diag(sub/match), 2=up(del), 3=left(ins), 4=transposition
    trace = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        p_val = pattern[i - 1]
        for j in range(1, n + 1):
            t_val = target[j - 1]

            # 1. Match / Mismatch
            is_eq = (p_val == t_val)
            sub_score = dp[i - 1][j - 1] + (match_score if is_eq else -mismatch_penalty)
            best_score = sub_score
            best_trace = 1
            best_start = start_pos[i - 1][j - 1]

            # 2. Deletion in target (step in pattern is missing in target)
            del_score = dp[i - 1][j] - gap_penalty
            if del_score > best_score:
                best_score = del_score
                best_trace = 2
                best_start = start_pos[i - 1][j]

            # 3. Insertion in target (extra step in target not in pattern)
            ins_score = dp[i][j - 1] - gap_penalty
            if ins_score > best_score:
                best_score = ins_score
                best_trace = 3
                best_start = start_pos[i][j - 1]

            # 4. Adjacent Transposition (Damerau extension)
            if i >= 2 and j >= 2:
                if pattern[i - 1] == target[j - 2] and pattern[i - 2] == target[j - 1]:
                    trans_score = dp[i - 2][j - 2] + transposition_score
                    if trans_score > best_score:
                        best_score = trans_score
                        best_trace = 4
                        best_start = start_pos[i - 2][j - 2]

            dp[i][j] = best_score
            trace[i][j] = best_trace
            start_pos[i][j] = best_start

    # The pattern must end at row m (all pattern steps accounted for)
    # Target can end at any j >= 1 (free end gap)
    best_end_j = 1
    max_final_score = dp[m][1]
    for j in range(2, n + 1):
        if dp[m][j] > max_final_score:
            max_final_score = dp[m][j]
            best_end_j = j

    # Traceback to count exact matches, transpositions, insertions, deletions
    matches = 0
    insertions = 0
    deletions = 0
    transpositions = 0

    curr_i = m
    curr_j = best_end_j

    matched_pattern_indices: List[int] = []
    missing_pattern_indices: List[int] = []
    max_consec_ins = 0
    curr_consec_ins = 0

    while curr_i > 0 and curr_j > 0:
        t = trace[curr_i][curr_j]
        if t == 1:
            if curr_consec_ins > max_consec_ins:
                max_consec_ins = curr_consec_ins
            curr_consec_ins = 0

            if pattern[curr_i - 1] == target[curr_j - 1]:
                matches += 1
                matched_pattern_indices.append(curr_i - 1)
            else:
                # Mismatch treated as substitution (1 del + 1 ins)
                deletions += 1
                insertions += 1
                missing_pattern_indices.append(curr_i - 1)
            curr_i -= 1
            curr_j -= 1
        elif t == 2:
            if curr_consec_ins > max_consec_ins:
                max_consec_ins = curr_consec_ins
            curr_consec_ins = 0

            deletions += 1
            missing_pattern_indices.append(curr_i - 1)
            curr_i -= 1
        elif t == 3:
            insertions += 1
            curr_consec_ins += 1
            curr_j -= 1
        elif t == 4:
            if curr_consec_ins > max_consec_ins:
                max_consec_ins = curr_consec_ins
            curr_consec_ins = 0

            transpositions += 2  # 2 steps involved in swap
            matched_pattern_indices.append(curr_i - 1)
            matched_pattern_indices.append(curr_i - 2)
            curr_i -= 2
            curr_j -= 2
        else:
            break

    if curr_consec_ins > max_consec_ins:
        max_consec_ins = curr_consec_ins

    # Remaining deletions if curr_i > 0
    if curr_i > 0:
        deletions += curr_i
        for idx in range(curr_i):
            missing_pattern_indices.append(idx)

    matched_pattern_indices.sort()
    missing_pattern_indices.sort()

    start_j = curr_j
    end_j = best_end_j
    window_len = max(1, end_j - start_j)

    # Compute normalized similarity
    # Perfect match: matches == m and window_len == m -> similarity = 1.0
    # Transposition: small penalty (each swapped pair gets 95% credit)
    effective_matches = matches + (transpositions * 0.95)
    # Normalized against (pattern length + window length) / 2
    similarity = round(min(1.0, max(0.0, (2.0 * effective_matches) / (m + window_len))), 4)

    # Coverage requires at least min_coverage fraction of pattern steps accounted for
    coverage = (matches + transpositions) / m
    is_match = (
        (similarity >= similarity_threshold)
        and (coverage >= min_coverage)
        and (max_consec_ins <= max_consecutive_insertions)
    )

    # Partial execution detection:
    # Captures significant prefix or partial subsequence (coverage in [0.35, 0.80))
    # with acceptable similarity without qualifying as a full repeated execution
    is_partial_match = (
        not is_match
        and matches >= 2
        and 0.35 <= coverage < 0.80
        and similarity >= 0.40
    )

    aligned_pattern = pattern
    aligned_target = target[start_j:end_j]

    return LocalAlignmentResult(
        similarity=similarity,
        start_idx=start_j,
        end_idx=end_j,
        aligned_pattern=aligned_pattern,
        aligned_target=aligned_target,
        matches=matches,
        insertions=insertions,
        deletions=deletions,
        transpositions=transpositions,
        is_match=is_match,
        is_partial_match=is_partial_match,
        matched_pattern_indices=matched_pattern_indices,
        missing_pattern_indices=missing_pattern_indices,
        max_consecutive_insertions=max_consec_ins,
    )


def find_all_local_occurrences(
    pattern: List[str],
    target: List[str],
    similarity_threshold: float = 0.80,
    min_coverage: float = 0.75,
    max_consecutive_insertions: int = 3,
) -> List[LocalAlignmentResult]:
    """
    Finds all non-overlapping local alignment occurrences of pattern within target.
    Allows measuring intra-session repetitions within a single session without
    inflating distinct-session occurrence counts.
    """
    occurrences: List[LocalAlignmentResult] = []
    current_offset = 0
    remaining_target = target

    while len(remaining_target) >= max(1, int(len(pattern) * min_coverage)):
        res = local_sequence_alignment(
            pattern=pattern,
            target=remaining_target,
            similarity_threshold=similarity_threshold,
            min_coverage=min_coverage,
            max_consecutive_insertions=max_consecutive_insertions,
        )
        if not res.is_match:
            break

        # Adjust indices to absolute offsets within original target
        adjusted_res = LocalAlignmentResult(
            similarity=res.similarity,
            start_idx=current_offset + res.start_idx,
            end_idx=current_offset + res.end_idx,
            aligned_pattern=res.aligned_pattern,
            aligned_target=res.aligned_target,
            matches=res.matches,
            insertions=res.insertions,
            deletions=res.deletions,
            transpositions=res.transpositions,
            is_match=True,
            is_partial_match=False,
            matched_pattern_indices=res.matched_pattern_indices,
            missing_pattern_indices=res.missing_pattern_indices,
            max_consecutive_insertions=res.max_consecutive_insertions,
        )
        occurrences.append(adjusted_res)

        # Advance beyond the matched window
        advance_by = max(1, res.end_idx)
        current_offset += advance_by
        remaining_target = remaining_target[advance_by:]

    return occurrences
