"""
Deterministic Python Comparators for Factual QA.

ARCHITECTURAL MANDATE:
- Pure Python deterministic comparison.
- The LLM is NEVER called to compare values or decide matches.
- All comparisons are fully transparent, repeatable, and unit-tested.
"""

from datetime import date, datetime
import re
from typing import Any, Dict, Optional, Tuple

from app.factual.exceptions import ComparisonError


WORD_TO_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90, "hundred": 100, "thousand": 1000
}


class DeterministicComparator:
    """
    Evaluates observed factual claims against expected ground-truth values
    using deterministic rules.
    """

    def __init__(self, numeric_tolerance: float = 0.01):
        self.numeric_tolerance = numeric_tolerance

    def compare(
        self,
        expected: Any,
        observed: Any,
        method: Optional[str] = None,
        allow_semantic_variation: bool = False,
        criteria: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:
        """
        Execute deterministic comparison.
        
        Args:
            expected: Ground-truth expected value.
            observed: Observed claim extracted from transcript.
            method: Comparison method from check criteria.
            allow_semantic_variation: Whether semantic variation is permitted by CheckDefinition.
            criteria: Check criteria dictionary with auxiliary comparison parameters.
            
        Returns:
            Tuple of (is_match: bool, reason: str).
        """
        criteria = criteria or {}

        if expected is None:
            raise ComparisonError("Expected ground truth value cannot be None.")

        if observed is None:
            return False, f"Observed value is None/missing; expected {expected}."

        # Detect comparison strategy from method or type
        method_normalized = (method or "").lower().strip()

        if "numeric" in method_normalized or "currency" in method_normalized or isinstance(expected, (int, float)):
            return self._compare_numeric(expected, observed, criteria)

        if "email" in method_normalized:
            return self._compare_email(expected, observed)

        if "date" in method_normalized or isinstance(expected, date):
            return self._compare_date(expected, observed)

        if "boolean" in method_normalized or isinstance(expected, bool):
            return self._compare_boolean(expected, observed)

        if "placeholder" in method_normalized:
            return self._compare_placeholder(expected, observed)

        # Default string / categorical comparison
        return self._compare_string(
            expected,
            observed,
            allow_semantic_variation=allow_semantic_variation,
            criteria=criteria
        )

    def _compare_numeric(self, expected: Any, observed: Any, criteria: Dict[str, Any]) -> Tuple[bool, str]:
        norm_expected = self.normalize_number(expected)
        norm_observed = self.normalize_number(observed)

        if norm_expected is None:
            raise ComparisonError(f"Could not parse expected numeric value: {expected}")

        if norm_observed is None:
            return False, f"Could not parse observed claim '{observed}' as a numeric value."

        tolerance = criteria.get("tolerance", self.numeric_tolerance)
        diff = abs(norm_expected - norm_observed)

        if diff <= tolerance:
            return True, f"Numeric values match: expected {norm_expected}, observed {norm_observed} (diff {diff:.4f} <= {tolerance})."
        else:
            return False, f"Numeric mismatch: expected {norm_expected}, observed {norm_observed} (diff {diff:.4f} > {tolerance})."

    def _compare_email(self, expected: Any, observed: Any) -> Tuple[bool, str]:
        norm_exp = str(expected).strip().lower()
        norm_obs = str(observed).strip().lower()

        if norm_exp == norm_obs:
            return True, f"Email address matches: '{norm_exp}'"
        else:
            return False, f"Email mismatch: expected '{norm_exp}', observed '{norm_obs}'"

    def _compare_date(self, expected: Any, observed: Any) -> Tuple[bool, str]:
        date_exp = self.normalize_date(expected)
        date_obs = self.normalize_date(observed)

        if date_exp is None:
            raise ComparisonError(f"Could not parse expected date: {expected}")

        if date_obs is None:
            return False, f"Could not parse observed date '{observed}'."

        if date_exp == date_obs:
            return True, f"Dates match: {date_exp.isoformat()}"
        else:
            return False, f"Date mismatch: expected {date_exp.isoformat()}, observed {date_obs.isoformat()}"

    def _compare_boolean(self, expected: Any, observed: Any) -> Tuple[bool, str]:
        bool_exp = self.normalize_boolean(expected)
        bool_obs = self.normalize_boolean(observed)

        if bool_exp is None or bool_obs is None:
            return False, f"Boolean conversion failed: expected={expected}, observed={observed}"

        if bool_exp == bool_obs:
            return True, f"Boolean values match: {bool_exp}"
        else:
            return False, f"Boolean mismatch: expected {bool_exp}, observed {bool_obs}"

    def _compare_placeholder(self, expected: Any, observed: Any) -> Tuple[bool, str]:
        str_exp = str(expected).strip()
        str_obs = str(observed).strip()

        if str_exp == str_obs:
            return True, f"Redaction placeholder matches exactly: '{str_exp}'"
        else:
            return False, f"Redaction placeholder mismatch: expected '{str_exp}', observed '{str_obs}'"

    def _compare_string(
        self,
        expected: Any,
        observed: Any,
        allow_semantic_variation: bool,
        criteria: Dict[str, Any]
    ) -> Tuple[bool, str]:
        str_exp = self._clean_string(str(expected))
        str_obs = self._clean_string(str(observed))

        # 1. Exact normalized match
        if str_exp == str_obs:
            return True, f"String values match: '{expected}'"

        # 2. Strict mode (no semantic variation allowed)
        if not allow_semantic_variation:
            return False, f"String mismatch (semantic variation disabled): expected '{expected}', observed '{observed}'"

        # 3. Controlled semantic variation allowed
        # Check explicit synonyms or variations defined in check criteria
        allowed_variations = [self._clean_string(v) for v in criteria.get("allowed_variations", [])]
        if str_obs in allowed_variations:
            return True, f"Semantic variation match against allowed criteria variations: '{observed}'"

        # Check key terms / phrases if configured
        key_terms = [self._clean_string(t) for t in criteria.get("key_terms", [])]
        if key_terms and all(term in str_obs for term in key_terms):
            return True, f"Semantic variation match on required key terms: {key_terms}"

        # Substring / containment fallback if enabled
        if criteria.get("allow_substring", False) and (str_exp in str_obs or str_obs in str_exp):
            return True, f"Substring match permitted: '{observed}' matches '{expected}'"

        return False, f"String mismatch (semantic variation permitted, but criteria not met): expected '{expected}', observed '{observed}'"

    @staticmethod
    def _clean_string(s: str) -> str:
        s = s.lower().strip()
        s = re.sub(r"[^\w\s]", " ", s)
        s = re.sub(r"\s+", " ", s)
        return s.strip()

    @classmethod
    def normalize_number(cls, val: Any) -> Optional[float]:
        """Convert float, int, formatted currency, or verbal number to float."""
        if isinstance(val, (int, float)):
            return float(val)

        if not isinstance(val, str):
            return None

        text = val.strip().lower()

        # Check standard digits with optional currency symbols: "$42.90", "42.90/month", "$317"
        match = re.search(r"[-+]?\d*\.?\d+", text.replace(",", ""))
        if match:
            try:
                return float(match.group())
            except ValueError:
                pass

        # Parse verbal words: "forty two dollars and ninety cents" / "forty two dollars and ninety"
        verbal_num = cls._parse_verbal_currency(text)
        if verbal_num is not None:
            return verbal_num

        return None

    @classmethod
    def _parse_verbal_currency(cls, text: str) -> Optional[float]:
        # Clean text
        cleaned = text.lower().replace("-", " ").replace(",", "")
        words = cleaned.split()

        dollars = 0.0
        cents = 0.0

        if "dollar" in cleaned or "dollars" in cleaned:
            parts = re.split(r"dollars?", cleaned)
            dollars_part = parts[0].strip()
            cents_part = parts[1].strip() if len(parts) > 1 else ""

            d_val = cls._words_to_number(dollars_part.split())
            if d_val is not None:
                dollars = float(d_val)

            c_val = cls._words_to_number(cents_part.replace("and", "").replace("cents", "").split())
            if c_val is not None:
                cents = float(c_val) / 100.0

            return round(dollars + cents, 4)

        # General words to number
        num = cls._words_to_number(words)
        return float(num) if num is not None else None

    @staticmethod
    def _words_to_number(words: list[str]) -> Optional[int]:
        tokens = [w for w in words if w in WORD_TO_NUM]
        if not tokens:
            return None

        total = 0
        current = 0
        for token in tokens:
            val = WORD_TO_NUM[token]
            if val == 1000:
                current = (current if current != 0 else 1) * 1000
                total += current
                current = 0
            elif val == 100:
                current = (current if current != 0 else 1) * 100
            else:
                current += val
        total += current
        return total

    @staticmethod
    def normalize_date(val: Any) -> Optional[date]:
        if isinstance(val, date):
            return val
        if not isinstance(val, str):
            return None

        s = val.strip()
        formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
            "%d-%m-%Y", "%Y/%m/%d", "%d %B %Y", "%B %d, %Y"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def normalize_boolean(val: Any) -> Optional[bool]:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            s = val.strip().lower()
            if s in {"true", "yes", "1", "included", "active"}:
                return True
            if s in {"false", "no", "0", "not included", "omitted", "inactive"}:
                return False
        return None
