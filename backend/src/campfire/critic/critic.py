"""Main Safety Critic implementation."""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from .types import CriticDecision, CriticStatus, ChecklistResponse, ChecklistStep
from .policy import PolicyEngine


logger = logging.getLogger(__name__)


class SafetyCritic:
    """Safety Critic that validates responses before they are shown to users."""
    
    def __init__(self, policy_path: str = "policy.md"):
        """Initialize Safety Critic with policy engine."""
        self.policy_engine = PolicyEngine(policy_path)
        self.audit_log: List[Dict[str, Any]] = []
    
    def review_response(self, response: Dict[str, Any]) -> CriticDecision:
        """
        Review a response and return ALLOW/BLOCK decision.
        
        Args:
            response: The response to review, expected to contain 'checklist' and 'meta'
            
        Returns:
            CriticDecision with status, reasons, and recommendations
        """
        try:
            # Parse response into structured format
            checklist_response = self._parse_response(response)
            
            # Perform all validation checks
            decision = self._validate_response(checklist_response)
            
            # Log the decision for audit trail
            self._log_decision(response, decision)
            
            return decision
            
        except Exception as e:
            logger.error(f"Error in Safety Critic review: {e}")
            # Default to BLOCK on any error
            return CriticDecision(
                status=CriticStatus.BLOCK,
                reasons=[f"Internal error during review: {str(e)}"],
                fixes=["Contact system administrator"]
            )
    
    def _parse_response(self, response: Dict[str, Any]) -> ChecklistResponse:
        """Parse response into structured ChecklistResponse."""
        if not isinstance(response, dict):
            raise ValueError("Response must be a dictionary")
        
        checklist_data = response.get('checklist', [])
        meta_data = response.get('meta', {})
        
        if not isinstance(checklist_data, list):
            raise ValueError("Checklist must be a list")
        
        checklist_steps = []
        for step_data in checklist_data:
            if not isinstance(step_data, dict):
                raise ValueError("Each checklist step must be a dictionary")
            
            step = ChecklistStep(
                title=step_data.get('title', ''),
                action=step_data.get('action', ''),
                source=step_data.get('source'),
                caution=step_data.get('caution')
            )
            checklist_steps.append(step)
        
        return ChecklistResponse(checklist=checklist_steps, meta=meta_data)
    
    def _validate_response(self, response: ChecklistResponse) -> CriticDecision:
        """Perform comprehensive validation of the response."""
        reasons = []
        fixes = []
        emergency_detected = False
        requires_emergency_banner = False
        
        # 1. Citation validation
        citation_issues = self._validate_citations(response.checklist)
        if citation_issues:
            reasons.extend(citation_issues)
            fixes.append("Ensure every step includes a valid source citation")
        
        # 2. Emergency keyword detection (informational, not blocking)
        emergency_keywords = self._detect_emergency_content(response)
        if emergency_keywords:
            emergency_detected = True
            requires_emergency_banner = True
            # Note: Emergency keywords don't block the response, just require banner
        
        # 3. Scope validation
        scope_issues = self._validate_scope(response)
        if scope_issues:
            reasons.extend(scope_issues)
            fixes.append("Keep content within first-aid and preparedness scope")
        
        # 4. Medical disclaimer validation
        disclaimer_issues = self._validate_disclaimers(response.meta)
        if disclaimer_issues:
            reasons.extend(disclaimer_issues)
            fixes.append("Include proper medical disclaimers")
        
        # 5. Content safety validation
        safety_issues = self._validate_content_safety(response)
        if safety_issues:
            reasons.extend(safety_issues)
            fixes.append("Remove inappropriate medical advice")
        
        # Determine final status
        if reasons:
            status = CriticStatus.BLOCK
        else:
            status = CriticStatus.ALLOW
            reasons = ["Response meets all safety criteria"]
        
        return CriticDecision(
            status=status,
            reasons=reasons,
            fixes=fixes if fixes else None,
            emergency_detected=emergency_detected,
            requires_emergency_banner=requires_emergency_banner
        )
    
    def _validate_citations(self, checklist: List[ChecklistStep]) -> List[str]:
        """Validate that all steps have proper citations."""
        issues = []
        
        if not self.policy_engine.config.citation_required:
            return issues
        
        for i, step in enumerate(checklist, 1):
            if not step.source:
                issues.append(f"Step {i} lacks source citation")
                continue
            
            if not isinstance(step.source, dict):
                issues.append(f"Step {i} has invalid source format")
                continue
            
            # Check for required source fields
            if not step.source.get('doc_id'):
                issues.append(f"Step {i} missing document ID in source")
            
            loc = step.source.get('loc')
            if not loc:
                issues.append(f"Step {i} missing location in source")
            elif not isinstance(loc, list) or len(loc) != 2 or not all(isinstance(x, int) for x in loc):
                issues.append(f"Step {i} has invalid location format in source")
        
        return issues
    
    def _detect_emergency_content(self, response: ChecklistResponse) -> List[str]:
        """Detect emergency keywords in the response content."""
        all_text = []
        
        # Collect all text from the response
        for step in response.checklist:
            all_text.extend([step.title, step.action])
            if step.caution:
                all_text.append(step.caution)
        
        # Add meta content
        for value in response.meta.values():
            if isinstance(value, str):
                all_text.append(value)
        
        # Check for emergency keywords
        detected_keywords = []
        full_text = ' '.join(filter(None, all_text))
        
        keywords = self.policy_engine.detect_emergency_keywords(full_text)
        detected_keywords.extend(keywords)
        
        return detected_keywords
    
    def _validate_scope(self, response: ChecklistResponse) -> List[str]:
        """Validate that content stays within first-aid/preparedness scope."""
        issues = []
        
        # Collect all text for scope checking
        all_text = []
        for step in response.checklist:
            all_text.extend([step.title, step.action])
            if step.caution:
                all_text.append(step.caution)
        
        full_text = ' '.join(filter(None, all_text))
        
        # Check for blocked medical phrases (this is the main scope violation)
        blocked_phrases = self.policy_engine.detect_blocked_phrases(full_text)
        if blocked_phrases:
            issues.append(f"Contains inappropriate medical terms: {', '.join(blocked_phrases)}")
        
        # Only flag scope issues if there are blocked phrases
        # Don't require explicit scope keywords for valid first-aid content
        
        return issues
    
    def _validate_disclaimers(self, meta: Dict[str, Any]) -> List[str]:
        """Validate that proper disclaimers are included."""
        issues = []
        
        disclaimer = meta.get('disclaimer', '')
        if not disclaimer:
            issues.append("Missing medical disclaimer")
            return issues
        
        disclaimer_lower = disclaimer.lower()
        
        # Check for required disclaimer phrases
        if "not medical advice" not in disclaimer_lower:
            issues.append("Disclaimer must include 'Not medical advice'")
        
        return issues
    
    def _validate_content_safety(self, response: ChecklistResponse) -> List[str]:
        """Validate content for safety issues."""
        issues = []
        
        # Check for empty or minimal content
        if not response.checklist:
            issues.append("Response contains no actionable steps")
        
        # Check for steps without actions
        for i, step in enumerate(response.checklist, 1):
            if not step.action or not step.action.strip():
                issues.append(f"Step {i} has no action specified")
            
            if not step.title or not step.title.strip():
                issues.append(f"Step {i} has no title specified")
        
        return issues
    
    def _log_decision(self, response: Dict[str, Any], decision: CriticDecision) -> None:
        """Log the critic decision for audit trail."""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': decision.status.value,
            'reasons': decision.reasons,
            'fixes': decision.fixes,
            'emergency_detected': decision.emergency_detected,
            'requires_emergency_banner': decision.requires_emergency_banner,
            'response_summary': {
                'checklist_steps': len(response.get('checklist', [])),
                'has_meta': bool(response.get('meta'))
            }
        }
        
        self.audit_log.append(log_entry)
        
        # Keep only last 1000 entries to prevent memory issues
        if len(self.audit_log) > 1000:
            self.audit_log = self.audit_log[-1000:]
        
        logger.info(f"Safety Critic decision: {decision.status.value} - {decision.reasons}")
    
    def get_audit_log(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get the audit log entries."""
        if limit:
            return self.audit_log[-limit:]
        return self.audit_log.copy()
    
    def get_safe_fallback_message(self) -> Dict[str, Any]:
        """Get a safe fallback message when responses are blocked."""
        return {
            'checklist': [
                {
                    'title': 'Seek Professional Help',
                    'action': 'Contact local emergency services or healthcare professionals for guidance.',
                    'source': None,
                    'caution': 'This system cannot provide appropriate guidance for your situation.'
                }
            ],
            'meta': {
                'disclaimer': self.policy_engine.get_medical_disclaimer(),
                'when_to_call_emergency': 'Call emergency services immediately for any life-threatening situation.',
                'blocked_by_safety_critic': True
            }
        }