"""Policy engine for Safety Critic system."""

import os
import re
from pathlib import Path
from typing import List, Set, Dict, Any
from dataclasses import dataclass


@dataclass
class PolicyConfig:
    """Configuration loaded from policy.md file."""
    emergency_keywords: Set[str]
    blocked_phrases: Set[str]
    required_disclaimers: List[str]
    scope_keywords: Set[str]
    citation_required: bool = True


class PolicyEngine:
    """Loads and manages safety policies from configuration files."""
    
    def __init__(self, policy_path: str = "policy.md"):
        """Initialize policy engine with configuration file path."""
        self.policy_path = policy_path
        self.config = self._load_default_config()
        
        # Try to load from file if it exists
        if os.path.exists(policy_path):
            self._load_from_file(policy_path)
    
    def _load_default_config(self) -> PolicyConfig:
        """Load default safety policy configuration."""
        return PolicyConfig(
            emergency_keywords={
                "unconscious", "unconsciousness", "not breathing", "no pulse",
                "chest pain", "heart attack", "cardiac arrest", "stroke",
                "severe bleeding", "hemorrhage", "anaphylaxis", "allergic reaction",
                "suicide", "suicidal", "overdose", "poisoning", "electric shock",
                "electrocution", "choking", "airway obstruction", "seizure",
                "head injury", "spinal injury", "broken bone", "fracture",
                "burn", "severe burn", "hypothermia", "heat stroke"
            },
            blocked_phrases={
                "diagnose", "diagnosis", "prescribe", "prescription", "medication",
                "drug", "surgery", "operate", "medical treatment", "cure",
                "disease", "illness", "condition", "disorder", "syndrome"
            },
            required_disclaimers=[
                "Not medical advice",
                "Call local emergency services",
                "Seek professional help"
            ],
            scope_keywords={
                "first aid", "emergency", "preparedness", "safety", "help",
                "assistance", "guidance", "steps", "action", "response"
            },
            citation_required=True
        )
    
    def _load_from_file(self, policy_path: str) -> None:
        """Load policy configuration from markdown file."""
        try:
            with open(policy_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse emergency keywords section
            emergency_match = re.search(
                r'## Emergency Keywords\s*\n(.*?)(?=\n##|\Z)', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if emergency_match:
                keywords = self._extract_keywords(emergency_match.group(1))
                self.config.emergency_keywords.update(keywords)
            
            # Parse blocked phrases section
            blocked_match = re.search(
                r'## Blocked Phrases\s*\n(.*?)(?=\n##|\Z)', 
                content, 
                re.DOTALL | re.IGNORECASE
            )
            if blocked_match:
                phrases = self._extract_keywords(blocked_match.group(1))
                self.config.blocked_phrases.update(phrases)
                
        except Exception as e:
            print(f"Warning: Could not load policy file {policy_path}: {e}")
    
    def _extract_keywords(self, section: str) -> Set[str]:
        """Extract keywords from a markdown section."""
        keywords = set()
        
        # Extract from bullet points
        bullet_matches = re.findall(r'[-*]\s*(.+)', section)
        for match in bullet_matches:
            # Clean up the text and split on commas
            clean_text = re.sub(r'[`"\'()]', '', match.strip())
            keywords.update(word.strip().lower() for word in clean_text.split(','))
        
        # Extract from inline code blocks
        code_matches = re.findall(r'`([^`]+)`', section)
        for match in code_matches:
            keywords.add(match.strip().lower())
        
        return {k for k in keywords if k}  # Remove empty strings
    
    def detect_emergency_keywords(self, text: str) -> List[str]:
        """Detect emergency keywords in text."""
        text_lower = text.lower()
        detected = []
        
        for keyword in self.config.emergency_keywords:
            if keyword in text_lower:
                detected.append(keyword)
        
        return detected
    
    def detect_blocked_phrases(self, text: str) -> List[str]:
        """Detect blocked medical phrases in text."""
        text_lower = text.lower()
        detected = []
        
        for phrase in self.config.blocked_phrases:
            if phrase in text_lower:
                detected.append(phrase)
        
        return detected
    
    def is_within_scope(self, text: str) -> bool:
        """Check if text is within first-aid/preparedness scope."""
        text_lower = text.lower()
        
        # Check for blocked medical phrases first
        blocked_found = any(phrase in text_lower for phrase in self.config.blocked_phrases)
        if blocked_found:
            return False
        
        # If no blocked phrases, check for scope keywords or common first-aid terms
        scope_keywords_extended = self.config.scope_keywords.union({
            "apply", "pressure", "wound", "bleeding", "bandage", "clean", "cloth",
            "check", "breathing", "pulse", "conscious", "unconscious", "call",
            "services", "injury", "injured", "hurt", "pain", "cut", "burn",
            "spinal", "head", "chest", "emergency", "help", "assistance",
            "tap", "shout", "okay", "move", "person", "victim", "patient"
        })
        
        scope_found = any(keyword in text_lower for keyword in scope_keywords_extended)
        
        # If it contains first-aid related terms and no blocked phrases, it's in scope
        return scope_found
    
    def get_emergency_banner_text(self) -> str:
        """Get the emergency banner text for critical situations."""
        return "⚠️ EMERGENCY: Not medical advice. Call local emergency services now."
    
    def get_medical_disclaimer(self) -> str:
        """Get the standard medical disclaimer text."""
        return "⚠️ This is not medical advice. For medical emergencies, contact local emergency services."