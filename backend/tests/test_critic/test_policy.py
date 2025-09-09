"""Tests for the Policy Engine."""

import pytest
import tempfile
import os
from pathlib import Path

from campfire.critic.policy import PolicyEngine, PolicyConfig


class TestPolicyEngine:
    """Test cases for PolicyEngine."""
    
    def test_default_config_initialization(self):
        """Test that default configuration is loaded correctly."""
        engine = PolicyEngine("nonexistent_file.md")
        
        assert isinstance(engine.config, PolicyConfig)
        assert engine.config.citation_required is True
        assert "unconscious" in engine.config.emergency_keywords
        assert "chest pain" in engine.config.emergency_keywords
        assert "diagnose" in engine.config.blocked_phrases
        assert "Not medical advice" in engine.config.required_disclaimers
    
    def test_emergency_keyword_detection(self):
        """Test detection of emergency keywords in text."""
        engine = PolicyEngine()
        
        # Test positive cases
        text1 = "The patient is unconscious and not breathing"
        detected1 = engine.detect_emergency_keywords(text1)
        assert "unconscious" in detected1
        assert "not breathing" in detected1
        
        # Test case insensitive
        text2 = "CHEST PAIN and severe bleeding"
        detected2 = engine.detect_emergency_keywords(text2)
        assert "chest pain" in detected2
        assert "severe bleeding" in detected2
        
        # Test negative case
        text3 = "Apply a bandage to the minor cut"
        detected3 = engine.detect_emergency_keywords(text3)
        assert len(detected3) == 0
    
    def test_blocked_phrase_detection(self):
        """Test detection of blocked medical phrases."""
        engine = PolicyEngine()
        
        # Test positive cases
        text1 = "I will diagnose your condition and prescribe medication"
        detected1 = engine.detect_blocked_phrases(text1)
        assert "diagnose" in detected1
        assert "prescribe" in detected1
        
        # Test case insensitive
        text2 = "This DISEASE requires SURGERY"
        detected2 = engine.detect_blocked_phrases(text2)
        assert "disease" in detected2
        assert "surgery" in detected2
        
        # Test negative case
        text3 = "Apply first aid and seek help"
        detected3 = engine.detect_blocked_phrases(text3)
        assert len(detected3) == 0
    
    def test_scope_validation(self):
        """Test scope validation for first-aid content."""
        engine = PolicyEngine()
        
        # Test valid scope
        text1 = "Apply first aid and emergency preparedness steps"
        assert engine.is_within_scope(text1) is True
        
        # Test invalid scope (blocked phrases)
        text2 = "I will diagnose your disease and prescribe medication"
        assert engine.is_within_scope(text2) is False
        
        # Test no scope keywords
        text3 = "This is just random text about nothing"
        assert engine.is_within_scope(text3) is False
    
    def test_banner_and_disclaimer_text(self):
        """Test emergency banner and disclaimer text generation."""
        engine = PolicyEngine()
        
        banner = engine.get_emergency_banner_text()
        assert "EMERGENCY" in banner
        assert "Call local emergency services" in banner
        
        disclaimer = engine.get_medical_disclaimer()
        assert "not medical advice" in disclaimer.lower()
        assert "emergency services" in disclaimer.lower()
    
    def test_policy_file_loading(self):
        """Test loading policy from markdown file."""
        # Create temporary policy file
        policy_content = """
# Test Policy

## Emergency Keywords

- `test emergency`, `test keyword`
- `custom emergency`

## Blocked Phrases

- `test blocked`, `custom blocked`
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(policy_content)
            temp_path = f.name
        
        try:
            engine = PolicyEngine(temp_path)
            
            # Check that custom keywords were loaded
            assert "test emergency" in engine.config.emergency_keywords
            assert "custom emergency" in engine.config.emergency_keywords
            assert "test blocked" in engine.config.blocked_phrases
            assert "custom blocked" in engine.config.blocked_phrases
            
            # Check that defaults are still present
            assert "unconscious" in engine.config.emergency_keywords
            assert "diagnose" in engine.config.blocked_phrases
            
        finally:
            os.unlink(temp_path)
    
    def test_keyword_extraction(self):
        """Test keyword extraction from markdown sections."""
        engine = PolicyEngine()
        
        # Test bullet point extraction
        section1 = """
- `keyword1`, `keyword2`
- keyword3, keyword4
* another keyword
"""
        keywords1 = engine._extract_keywords(section1)
        assert "keyword1" in keywords1
        assert "keyword2" in keywords1
        assert "keyword3" in keywords1
        assert "keyword4" in keywords1
        assert "another keyword" in keywords1
        
        # Test inline code extraction
        section2 = "Some text with `inline code` and `another code`"
        keywords2 = engine._extract_keywords(section2)
        assert "inline code" in keywords2
        assert "another code" in keywords2
    
    def test_invalid_policy_file_handling(self):
        """Test handling of invalid or missing policy files."""
        # Test with non-existent file
        engine1 = PolicyEngine("nonexistent.md")
        assert isinstance(engine1.config, PolicyConfig)
        
        # Test with invalid file content
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Invalid content that will cause parsing issues")
            temp_path = f.name
        
        try:
            engine2 = PolicyEngine(temp_path)
            # Should still have default config
            assert isinstance(engine2.config, PolicyConfig)
            assert "unconscious" in engine2.config.emergency_keywords
            
        finally:
            os.unlink(temp_path)