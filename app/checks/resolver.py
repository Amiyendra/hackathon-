"""
Version Resolver module.

Resolves deterministic check versions active on a specific historical or current call date.
Guarantees:
- Never silently falls back to today's date or an alternative version.
- Explicitly rejects calls when no active version exists.
- Explicitly rejects configuration when multiple active versions match (overlapping ranges).
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Union

from app.checks.exceptions import NoMatchingVersionError, OverlappingVersionError
from app.checks.models import CheckDefinition, CheckLibrary, ResolvedRuleSet


class VersionResolver:
    """
    Resolves active check definitions and rule sets for a given retailer and call date.
    """

    def __init__(self, library: CheckLibrary):
        self.library = library

    @staticmethod
    def _coerce_date(target_date: Union[date, str]) -> date:
        if isinstance(target_date, str):
            try:
                return datetime.strptime(target_date.strip(), "%Y-%m-%d").date()
            except ValueError as e:
                raise ValueError(f"Invalid date string format: '{target_date}'. Expected 'YYYY-MM-DD'.") from e
        elif isinstance(target_date, date):
            return target_date
        else:
            raise ValueError(f"Invalid date type: {type(target_date).__name__}. Expected date or str.")

    def resolve_check(
        self,
        retailer: str,
        check_id: str,
        call_date: Union[date, str]
    ) -> CheckDefinition:
        """
        Resolve exactly one check version for a specific check ID on call_date.
        
        Args:
            retailer: Retailer code.
            check_id: Unique check ID.
            call_date: Historical or current call date (date or 'YYYY-MM-DD').
            
        Returns:
            The single active CheckDefinition.
            
        Raises:
            NoMatchingVersionError: If no version is active on call_date.
            OverlappingVersionError: If multiple versions match call_date.
        """
        eval_date = self._coerce_date(call_date)
        retailer_target = retailer.strip().upper()

        candidate_checks = [
            c for c in self.library.checks
            if c.retailer.upper() == retailer_target and c.check_id == check_id
        ]

        if not candidate_checks:
            raise NoMatchingVersionError(
                f"No check definitions exist for check '{check_id}' and retailer '{retailer}'."
            )

        active_matches = [c for c in candidate_checks if c.is_active_on(eval_date)]

        if len(active_matches) == 0:
            raise NoMatchingVersionError(
                f"No active version found for check '{check_id}' (retailer '{retailer}') on call date {eval_date}. "
                f"Available versions: {[f'{c.version} ({c.effective_from} to {c.effective_to})' for c in candidate_checks]}."
            )

        if len(active_matches) > 1:
            raise OverlappingVersionError(
                f"Multiple active versions found for check '{check_id}' (retailer '{retailer}') on call date {eval_date}: "
                f"{[c.version for c in active_matches]}."
            )

        return active_matches[0]

    def resolve_ruleset(
        self,
        retailer: str,
        call_date: Union[date, str]
    ) -> ResolvedRuleSet:
        """
        Resolve the complete active rule set for a retailer on call_date.
        
        Args:
            retailer: Retailer code.
            call_date: Historical or current call date (date or 'YYYY-MM-DD').
            
        Returns:
            ResolvedRuleSet containing all active check definitions.
            
        Raises:
            NoMatchingVersionError: If no active checks exist for the retailer on call_date.
            OverlappingVersionError: If multiple active versions match any check ID.
        """
        eval_date = self._coerce_date(call_date)
        retailer_target = retailer.strip().upper()

        retailer_checks = [c for c in self.library.checks if c.retailer.upper() == retailer_target]
        if not retailer_checks:
            raise NoMatchingVersionError(f"No checks registered in library for retailer '{retailer}'.")

        # Group by check_id
        checks_by_id: Dict[str, List[CheckDefinition]] = {}
        for c in retailer_checks:
            checks_by_id.setdefault(c.check_id, []).append(c)

        active_checks: List[CheckDefinition] = []
        for check_id, check_list in checks_by_id.items():
            matches = [c for c in check_list if c.is_active_on(eval_date)]
            if len(matches) > 1:
                raise OverlappingVersionError(
                    f"Multiple active versions found for check '{check_id}' (retailer '{retailer}') "
                    f"on call date {eval_date}: {[c.version for c in matches]}."
                )
            elif len(matches) == 1:
                active_checks.append(matches[0])

        if not active_checks:
            raise NoMatchingVersionError(
                f"No active checks resolved for retailer '{retailer}' on call date {eval_date}."
            )

        return ResolvedRuleSet(
            retailer=retailer_target,
            call_date=eval_date,
            checks=active_checks
        )
