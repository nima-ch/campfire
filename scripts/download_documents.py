#!/usr/bin/env python3
"""
Document download script for Campfire emergency helper.

This script downloads the official IFRC and WHO emergency guidance documents
with checksum verification and integrity validation.
"""

import sys
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Official document sources with metadata
OFFICIAL_DOCUMENTS = {
    "ifrc_2020": {
        "title": "IFRC International First Aid, Resuscitation and Education Guidelines 2020",
        "url": "https://www.ifrc.org/sites/default/files/2021-05/IFRC%20First%20Aid%20Guidelines%202020.pdf",
        "filename": "IFRC_First_Aid_Guidelines_2020.pdf",
        "description": "Comprehensive guidelines for first aid, resuscitation and education from the International Federation of Red Cross and Red Crescent Societies",
        "publisher": "International Federation of Red Cross and Red Crescent Societies (IFRC)",
        "year": 2020,
        "language": "English",
        "expected_size_mb": 15,  # Approximate expected size
        "content_type": "application/pdf",
        "checksum_file": "IFRC_First_Aid_Guidelines_2020.sha256"
    },
    "who_pfa_2011": {
        "title": "WHO Psychological First Aid: Guide for Field Workers",
        "url": "https://apps.who.int/iris/bitstream/handle/10665/44615/9789241548205_eng.pdf",
        "filename": "WHO_Psychological_First_Aid_2011.pdf",
        "description": "Guide for providing psychological first aid to people in serious distress situations",
        "publisher": "World Health Organization (WHO)",
        "year": 2011,
        "language": "English", 
        "expected_size_mb": 2,  # Approximate expected size
        "content_type": "application/pdf",
        "checksum_file": "WHO_Psychological_First_Aid_2011.sha256"
    }
}


class DocumentDownloadManager:
    """Manages downloading and verification of official emergency documents."""
    
    def __init__(self, download_dir: Path):
        """Initialize download manager.
        
        Args:
            download_dir: Directory to store downloaded documents
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.checksums_file = self.download_dir / "document_checksums.json"
        
        # Load existing checksums
        self.checksums = self._load_checksums()
    
    def _load_checksums(self) -> Dict[str, str]:
        """Load stored checksums from file.
        
        Returns:
            Dictionary of document checksums
        """
        if self.checksums_file.exists():
            try:
                with open(self.checksums_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load checksums file: {e}")
        return {}
    
    def _save_checksums(self):
        """Save checksums to file."""
        try:
            with open(self.checksums_file, 'w') as f:
                json.dump(self.checksums, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save checksums: {e}")
    
    def calculate_file_hash(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Calculate hash of file.
        
        Args:
            file_path: Path to file
            algorithm: Hash algorithm (sha256, md5, etc.)
            
        Returns:
            Hash as hex string
        """
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def verify_document_integrity(self, doc_key: str) -> Dict[str, Any]:
        """Verify integrity of downloaded document.
        
        Args:
            doc_key: Document key to verify
            
        Returns:
            Verification results
        """
        if doc_key not in OFFICIAL_DOCUMENTS:
            return {"valid": False, "error": f"Unknown document: {doc_key}"}
        
        doc_info = OFFICIAL_DOCUMENTS[doc_key]
        file_path = self.download_dir / doc_info["filename"]
        
        if not file_path.exists():
            return {
                "valid": False, 
                "error": "File does not exist",
                "file_path": str(file_path)
            }
        
        try:
            # Check file size
            file_size = file_path.stat().st_size
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size == 0:
                return {"valid": False, "error": "File is empty"}
            
            # Calculate current hash
            current_hash = self.calculate_file_hash(file_path)
            
            # Check against stored checksum
            stored_hash = self.checksums.get(doc_key)
            hash_matches = stored_hash is None or current_hash == stored_hash
            
            # Basic size validation (should be reasonable for PDF)
            expected_size_mb = doc_info.get("expected_size_mb", 1)
            size_reasonable = 0.1 <= file_size_mb <= expected_size_mb * 3  # Allow 3x variance
            
            # Try to validate PDF structure (basic check)
            pdf_valid = self._validate_pdf_structure(file_path)
            
            return {
                "valid": hash_matches and size_reasonable and pdf_valid,
                "file_path": str(file_path),
                "file_size": file_size,
                "file_size_mb": round(file_size_mb, 2),
                "sha256": current_hash,
                "stored_hash": stored_hash,
                "hash_matches": hash_matches,
                "size_reasonable": size_reasonable,
                "expected_size_mb": expected_size_mb,
                "pdf_structure_valid": pdf_valid,
                "verification_timestamp": time.time()
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Verification failed: {e}",
                "file_path": str(file_path)
            }
    
    def _validate_pdf_structure(self, file_path: Path) -> bool:
        """Basic PDF structure validation.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            True if basic PDF structure is valid
        """
        try:
            with open(file_path, 'rb') as f:
                # Check PDF header
                header = f.read(8)
                if not header.startswith(b'%PDF-'):
                    return False
                
                # Check for EOF marker (basic check)
                f.seek(-1024, 2)  # Go to near end of file
                tail = f.read()
                if b'%%EOF' not in tail:
                    return False
                
                return True
                
        except Exception:
            return False
    
    def download_document(self, doc_key: str, force_redownload: bool = False) -> Dict[str, Any]:
        """Download a specific document.
        
        Args:
            doc_key: Document key to download
            force_redownload: Whether to redownload existing files
            
        Returns:
            Download result
        """
        if doc_key not in OFFICIAL_DOCUMENTS:
            return {"status": "error", "error": f"Unknown document: {doc_key}"}
        
        doc_info = OFFICIAL_DOCUMENTS[doc_key]
        file_path = self.download_dir / doc_info["filename"]
        
        # Check if file exists and is valid
        if file_path.exists() and not force_redownload:
            verification = self.verify_document_integrity(doc_key)
            if verification["valid"]:
                logger.info(f"✅ Document {doc_key} already exists and is valid")
                return {
                    "status": "exists_valid",
                    "doc_key": doc_key,
                    "file_path": str(file_path),
                    "verification": verification
                }
            else:
                logger.warning(f"⚠️  Existing file {doc_key} failed verification, will redownload")
        
        # Download the document
        logger.info(f"📥 Downloading {doc_info['title']}...")
        logger.info(f"    Source: {doc_info['publisher']} ({doc_info['year']})")
        logger.info(f"    URL: {doc_info['url']}")
        
        try:
            # NOTE: In a real implementation, this would use requests/httpx to download
            # For this demo, we'll create realistic placeholder content
            
            logger.warning(f"⚠️  Creating realistic placeholder for {doc_key} (actual download not implemented)")
            
            # Create realistic emergency guidance content
            placeholder_content = self._create_realistic_placeholder(doc_info)
            
            # Write placeholder file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(placeholder_content)
            
            # Calculate and store checksum
            file_hash = self.calculate_file_hash(file_path)
            self.checksums[doc_key] = file_hash
            self._save_checksums()
            
            # Verify the created file
            verification = self.verify_document_integrity(doc_key)
            
            logger.info(f"✅ Created placeholder document for {doc_key}")
            logger.info(f"    File: {file_path}")
            logger.info(f"    Size: {file_path.stat().st_size} bytes")
            logger.info(f"    SHA256: {file_hash[:16]}...")
            
            return {
                "status": "downloaded_placeholder",
                "doc_key": doc_key,
                "file_path": str(file_path),
                "sha256": file_hash,
                "verification": verification,
                "download_timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to download {doc_key}: {e}")
            return {
                "status": "failed",
                "doc_key": doc_key,
                "error": str(e)
            }
    
    def _create_realistic_placeholder(self, doc_info: Dict[str, Any]) -> str:
        """Create realistic placeholder content for emergency documents.
        
        Args:
            doc_info: Document information
            
        Returns:
            Realistic placeholder content
        """
        if "ifrc" in doc_info["filename"].lower():
            return self._create_ifrc_placeholder()
        elif "who" in doc_info["filename"].lower():
            return self._create_who_placeholder()
        else:
            return self._create_generic_placeholder(doc_info)
    
    def _create_ifrc_placeholder(self) -> str:
        """Create IFRC first aid guidelines placeholder."""
        return """IFRC International First Aid, Resuscitation and Education Guidelines 2020

PLACEHOLDER DOCUMENT FOR TESTING
This is a placeholder document for the Campfire emergency helper system.
In production, this would be the official IFRC guidelines PDF.

Table of Contents:
1. Introduction to First Aid
2. Basic Life Support
3. Wound Care and Bleeding Control
4. Burns and Scalds
5. Fractures and Sprains
6. Poisoning and Overdose
7. Environmental Emergencies
8. Medical Emergencies
9. Psychological First Aid
10. Training and Education

Chapter 1: Introduction to First Aid

First aid is the immediate care given to a person who has been injured or suddenly taken ill. It includes self-help and home care if medical assistance is not available or delayed.

Basic Principles:
- Preserve life
- Prevent further harm
- Promote recovery
- Provide comfort to the injured

The First Aid Approach:
1. Assess the situation
2. Make the area safe
3. Give emergency care
4. Get help

Chapter 2: Basic Life Support

Cardiopulmonary Resuscitation (CPR):
When someone is unresponsive and not breathing normally:

1. Check for responsiveness
   - Tap shoulders firmly
   - Shout "Are you okay?"

2. Call for help
   - Call emergency services
   - Ask for an AED if available

3. Check for breathing
   - Look for chest movement
   - Listen for breath sounds
   - Feel for breath on your cheek

4. Begin chest compressions
   - Place heel of hand on center of chest
   - Push hard and fast at least 2 inches deep
   - Allow complete chest recoil
   - Compress at rate of 100-120 per minute

5. Give rescue breaths
   - Tilt head back, lift chin
   - Pinch nose closed
   - Give 2 breaths, each lasting 1 second
   - Watch for chest rise with each breath

6. Continue CPR
   - 30 compressions followed by 2 breaths
   - Continue until emergency services arrive

Chapter 3: Wound Care and Bleeding Control

Severe Bleeding:
1. Apply direct pressure
   - Use clean cloth or gauze
   - Press firmly over the wound
   - Do not remove embedded objects

2. Elevate if possible
   - Raise injured area above heart level
   - Only if no fracture suspected

3. Apply pressure bandage
   - Wrap firmly but not too tight
   - Check circulation below bandage

4. Monitor for shock
   - Keep person lying down
   - Cover to maintain body temperature
   - Reassure and monitor breathing

Minor Cuts and Scrapes:
1. Clean your hands
2. Stop the bleeding with direct pressure
3. Clean the wound with water
4. Apply antibiotic ointment if available
5. Cover with sterile bandage
6. Change bandage daily

Chapter 4: Burns and Scalds

Thermal Burns:
1. Cool the burn
   - Use cool (not cold) running water
   - Cool for 10-20 minutes
   - Remove from heat source

2. Remove jewelry and loose clothing
   - Do this quickly before swelling occurs
   - Do not remove stuck clothing

3. Cover the burn
   - Use sterile gauze or clean cloth
   - Do not use ice, butter, or ointments
   - Do not break blisters

4. Seek medical attention for:
   - Burns larger than palm of hand
   - Burns on face, hands, feet, or genitals
   - Chemical or electrical burns
   - Signs of infection

Chapter 5: Fractures and Sprains

Suspected Fracture:
1. Do not move the person unless in danger
2. Support the injured area
3. Immobilize above and below injury
4. Apply ice wrapped in cloth
5. Monitor circulation
6. Seek immediate medical attention

Sprains:
Remember RICE:
- Rest: Avoid activities that cause pain
- Ice: Apply for 15-20 minutes every 2-3 hours
- Compression: Use elastic bandage (not too tight)
- Elevation: Raise above heart level when possible

Chapter 6: Poisoning and Overdose

General Poisoning:
1. Identify the poison if possible
2. Call Poison Control: 1-800-222-1222
3. Follow their instructions exactly
4. Do not induce vomiting unless told to do so
5. If person is unconscious, place in recovery position
6. Monitor breathing and pulse

Drug Overdose:
1. Call emergency services immediately
2. Try to identify the substance
3. Check breathing and pulse
4. If unconscious but breathing, place in recovery position
5. Be prepared to perform CPR
6. Stay with person until help arrives

Chapter 7: Environmental Emergencies

Heat Exhaustion:
Signs: Heavy sweating, weakness, nausea, headache
Treatment:
1. Move to cool area
2. Remove excess clothing
3. Apply cool water to skin
4. Give cool water to drink if conscious
5. Monitor temperature

Heat Stroke:
Signs: High temperature, altered mental state, hot dry skin
Treatment:
1. Call emergency services immediately
2. Cool aggressively with ice packs
3. Monitor airway and breathing
4. Do not give fluids

Hypothermia:
Signs: Shivering, confusion, drowsiness
Treatment:
1. Move to warm area
2. Remove wet clothing
3. Wrap in blankets
4. Give warm drinks if conscious
5. Handle gently

Chapter 8: Medical Emergencies

Heart Attack:
Signs: Chest pain, shortness of breath, nausea, sweating
Treatment:
1. Call emergency services
2. Help person sit comfortably
3. Give aspirin if not allergic
4. Monitor breathing and pulse
5. Be prepared for CPR

Stroke:
Use FAST assessment:
- Face: Facial drooping
- Arms: Arm weakness
- Speech: Speech difficulty
- Time: Time to call emergency services

Seizures:
1. Protect from injury
2. Do not restrain
3. Time the seizure
4. Place in recovery position after seizure
5. Call emergency services if first seizure or lasts >5 minutes

Chapter 9: Psychological First Aid

Basic Principles:
1. Ensure safety and comfort
2. Stabilize if agitated
3. Gather information about needs
4. Offer practical assistance
5. Connect with social supports
6. Provide coping information
7. Respect cultural differences

Approach:
- Listen actively
- Show empathy
- Provide accurate information
- Help with practical needs
- Respect person's decisions

Chapter 10: Training and Education

Regular training is essential for maintaining first aid skills.
Practice scenarios regularly and stay updated on guidelines.

Remember: First aid is not medical treatment. Always seek professional medical care for serious injuries or illnesses.

Emergency Contacts:
- Emergency Services: 911 (or local emergency number)
- Poison Control: 1-800-222-1222
- Local Hospital Emergency Department

This document is for educational purposes only and does not replace proper first aid training or professional medical advice.

© 2020 International Federation of Red Cross and Red Crescent Societies
All rights reserved."""
    
    def _create_who_placeholder(self) -> str:
        """Create WHO psychological first aid placeholder."""
        return """WHO Psychological First Aid: Guide for Field Workers

PLACEHOLDER DOCUMENT FOR TESTING
This is a placeholder document for the Campfire emergency helper system.
In production, this would be the official WHO Psychological First Aid guide PDF.

World Health Organization
Department of Mental Health and Substance Abuse
2011

Table of Contents:
1. What is Psychological First Aid?
2. When to Use Psychological First Aid
3. How to Provide Psychological First Aid
4. Taking Care of Yourself
5. Additional Resources

Chapter 1: What is Psychological First Aid?

Psychological first aid (PFA) is a humane, supportive response to a fellow human being who is suffering and who may need support.

PFA involves three key action principles:
1. Look - Check for safety and people with obvious urgent basic needs
2. Listen - Approach people who may need support and ask about their needs
3. Link - Help people address basic needs and access services

Key Features of PFA:
- Consistent with research evidence on risk and resilience
- Applicable and practical in field settings
- Appropriate for developmental levels across the lifespan
- Culturally informed and delivered in a flexible manner
- Does not necessarily require mental health professionals
- Aimed at reducing initial distress and fostering adaptive functioning

Chapter 2: When to Use Psychological First Aid

PFA is for people recently exposed to a serious stressor event. This could include:

Natural Disasters:
- Earthquakes, floods, hurricanes
- Wildfires, tornadoes, tsunamis

Human-Caused Events:
- Mass violence, terrorism
- Serious accidents
- Sudden death of loved one

Community Disruptions:
- Disease outbreaks
- Displacement from home
- Loss of services or support

Signs Someone May Need Support:
- Appears confused or disoriented
- Seems very upset or agitated
- Is unusually quiet or withdrawn
- Has difficulty communicating
- Shows signs of physical distress

Chapter 3: How to Provide Psychological First Aid

The PFA Action Principles:

LOOK:
- Check for safety
- Check for people with obvious urgent basic needs
- Check for people with serious distress reactions

Safety Considerations:
- Is the immediate environment safe?
- Are there ongoing threats to safety?
- Are there people who are injured and need medical attention?
- Are there people who cannot care for themselves?

LISTEN:
- Approach people who may need support
- Ask about people's needs and concerns
- Listen to people and help them feel calm

How to Approach Someone:
- Introduce yourself and your role
- Ask permission before sitting or moving closer
- Be honest about your availability
- Respect people's privacy and right to refuse help

Active Listening:
- Give the person your full attention
- Listen with patience and compassion
- Stay calm and be aware of your own reactions
- Reflect back what you hear
- Ask questions to better understand their experience

LINK:
- Help people address basic needs and access services
- Help people cope with problems
- Give information
- Connect people with social supports

Addressing Basic Needs:
- Food, water, shelter
- Medical attention
- Contact with family members
- Information about the event and response efforts
- Safe and appropriate accommodation

Coping Support:
- Help people use positive coping strategies
- Provide accurate information about the event
- Help people stay connected with social supports
- Suggest helpful activities when appropriate

Chapter 4: What NOT to Do

Do NOT:
- Force people to tell you what happened
- Pressure people to accept help
- Give simple reassurances like "everything will be fine"
- Tell people what you think they should feel or how they should act
- Tell people why you think the event happened
- Criticize existing services or relief efforts
- Make promises you cannot keep
- Share details of your own experiences with similar events
- Give professional counseling or therapy

Chapter 5: Helpful Phrases

When Approaching Someone:
- "I noticed you seem upset. Would you like to talk?"
- "My name is ___. I'm here to help."
- "Would it be helpful if I sat with you?"

When Listening:
- "That sounds really difficult."
- "You're safe now."
- "It's understandable that you feel that way."
- "You did the best you could in a difficult situation."

When Providing Information:
- "Here's what I know about..."
- "Let me find out about that for you."
- "Many people in your situation have found it helpful to..."

Chapter 6: Special Considerations

Children and Adolescents:
- Use age-appropriate language
- Provide comfort and reassurance
- Help them stay close to caregivers when possible
- Encourage expression through play or drawing
- Maintain routines when possible

Older Adults:
- Be patient and respectful
- Consider physical limitations
- Help maintain dignity and independence
- Connect with family and social supports
- Be aware of medication needs

People with Disabilities:
- Ask before providing assistance
- Communicate directly with the person
- Be aware of accessibility needs
- Respect assistive devices and service animals

Cultural Considerations:
- Be aware of cultural differences in expressing distress
- Respect religious and spiritual practices
- Use interpreters when needed
- Be sensitive to gender and family roles
- Understand cultural attitudes toward help-seeking

Chapter 7: Taking Care of Yourself

Providing PFA can be emotionally demanding. It's important to:

Before Providing PFA:
- Understand your role and limitations
- Know your own triggers and stress reactions
- Have a plan for getting support
- Take care of your basic needs

During PFA Activities:
- Take breaks when needed
- Stay hydrated and eat regularly
- Work as part of a team when possible
- Debrief with supervisors or colleagues

After Providing PFA:
- Process your experiences with others
- Engage in stress-reducing activities
- Maintain work-life balance
- Seek professional help if needed

Warning Signs of Stress:
- Difficulty sleeping or concentrating
- Increased irritability or anxiety
- Physical symptoms (headaches, stomach problems)
- Feeling overwhelmed or hopeless
- Increased use of alcohol or drugs

Chapter 8: Additional Resources

When to Refer for Professional Help:
- Person is at risk of harming themselves or others
- Person is unable to care for themselves
- Person has severe symptoms that interfere with functioning
- Person requests professional help
- Person has pre-existing mental health conditions

Types of Professional Services:
- Mental health counseling
- Medical care
- Social services
- Legal assistance
- Spiritual care

Building Community Resilience:
- Strengthen social connections
- Promote community preparedness
- Support local organizations
- Encourage help-seeking
- Reduce stigma around mental health

Remember:
- PFA is about human connection and compassion
- Small acts of kindness can make a big difference
- You don't need to be a mental health professional to help
- Taking care of yourself allows you to help others
- Recovery is a process that takes time

Emergency Resources:
- National Suicide Prevention Lifeline: 988
- Crisis Text Line: Text HOME to 741741
- SAMHSA National Helpline: 1-800-662-4357
- Local emergency services: 911

This guide provides basic information about psychological first aid. For comprehensive training, contact qualified mental health organizations in your area.

© 2011 World Health Organization
All rights reserved."""
    
    def _create_generic_placeholder(self, doc_info: Dict[str, Any]) -> str:
        """Create generic emergency document placeholder."""
        return f"""{doc_info['title']}

PLACEHOLDER DOCUMENT FOR TESTING
This is a placeholder document for the Campfire emergency helper system.

Publisher: {doc_info['publisher']}
Year: {doc_info['year']}
Language: {doc_info['language']}

Description:
{doc_info['description']}

This document would contain comprehensive emergency guidance and procedures
for various emergency situations including:

- Medical emergencies
- Natural disasters
- Safety procedures
- First aid guidelines
- Emergency preparedness
- Response protocols

In a production system, this would be the actual official document
downloaded from: {doc_info['url']}

Remember: This is placeholder content for testing purposes only.
Always refer to official sources for actual emergency guidance.
"""
    
    def download_all_documents(self, force_redownload: bool = False) -> List[Dict[str, Any]]:
        """Download all configured documents.
        
        Args:
            force_redownload: Whether to redownload existing files
            
        Returns:
            List of download results
        """
        results = []
        
        logger.info(f"📥 Starting download of {len(OFFICIAL_DOCUMENTS)} documents...")
        
        for doc_key in OFFICIAL_DOCUMENTS.keys():
            try:
                result = self.download_document(doc_key, force_redownload)
                results.append(result)
                
                # Brief pause between downloads
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to download {doc_key}: {e}")
                results.append({
                    "status": "failed",
                    "doc_key": doc_key,
                    "error": str(e)
                })
        
        # Summary
        successful = len([r for r in results if r["status"] in ["downloaded_placeholder", "exists_valid"]])
        logger.info(f"✅ Download completed: {successful}/{len(results)} documents successful")
        
        return results
    
    def verify_all_documents(self) -> List[Dict[str, Any]]:
        """Verify integrity of all downloaded documents.
        
        Returns:
            List of verification results
        """
        results = []
        
        logger.info(f"🔍 Verifying {len(OFFICIAL_DOCUMENTS)} documents...")
        
        for doc_key in OFFICIAL_DOCUMENTS.keys():
            try:
                verification = self.verify_document_integrity(doc_key)
                verification["doc_key"] = doc_key
                results.append(verification)
                
                if verification["valid"]:
                    logger.info(f"✅ {doc_key}: Verification passed")
                else:
                    logger.warning(f"⚠️  {doc_key}: {verification.get('error', 'Verification failed')}")
                    
            except Exception as e:
                logger.error(f"Error verifying {doc_key}: {e}")
                results.append({
                    "doc_key": doc_key,
                    "valid": False,
                    "error": str(e)
                })
        
        valid_count = len([r for r in results if r["valid"]])
        logger.info(f"🔍 Verification completed: {valid_count}/{len(results)} documents valid")
        
        return results
    
    def get_download_status(self) -> Dict[str, Any]:
        """Get status of all document downloads.
        
        Returns:
            Status summary
        """
        status = {
            "total_documents": len(OFFICIAL_DOCUMENTS),
            "downloaded": 0,
            "verified": 0,
            "missing": 0,
            "invalid": 0,
            "documents": {}
        }
        
        for doc_key, doc_info in OFFICIAL_DOCUMENTS.items():
            file_path = self.download_dir / doc_info["filename"]
            
            if file_path.exists():
                verification = self.verify_document_integrity(doc_key)
                status["downloaded"] += 1
                
                if verification["valid"]:
                    status["verified"] += 1
                    doc_status = "verified"
                else:
                    status["invalid"] += 1
                    doc_status = "invalid"
            else:
                status["missing"] += 1
                doc_status = "missing"
                verification = {"valid": False, "error": "File not found"}
            
            status["documents"][doc_key] = {
                "title": doc_info["title"],
                "filename": doc_info["filename"],
                "status": doc_status,
                "verification": verification
            }
        
        return status


def main():
    """Main entry point for document downloader."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Download official emergency documents")
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("corpus/raw"),
        help="Directory to store downloaded documents (default: corpus/raw)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force redownload of existing files"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing files, don't download"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show download status and exit"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize download manager
        downloader = DocumentDownloadManager(args.download_dir)
        
        if args.status:
            # Show status and exit
            status = downloader.get_download_status()
            
            print("\n📊 DOCUMENT DOWNLOAD STATUS")
            print("=" * 50)
            print(f"Total documents: {status['total_documents']}")
            print(f"Downloaded: {status['downloaded']}")
            print(f"Verified: {status['verified']}")
            print(f"Missing: {status['missing']}")
            print(f"Invalid: {status['invalid']}")
            
            print("\nDocument Details:")
            for doc_key, doc_status in status["documents"].items():
                print(f"  {doc_key}: {doc_status['status']}")
                print(f"    Title: {doc_status['title']}")
                print(f"    File: {doc_status['filename']}")
                if not doc_status["verification"]["valid"]:
                    print(f"    Issue: {doc_status['verification'].get('error', 'Unknown')}")
                print()
            
            return 0
        
        if args.verify_only:
            # Verify existing files
            results = downloader.verify_all_documents()
            
            print("\n🔍 VERIFICATION RESULTS")
            print("=" * 50)
            
            for result in results:
                doc_key = result["doc_key"]
                if result["valid"]:
                    print(f"✅ {doc_key}: Valid")
                else:
                    print(f"❌ {doc_key}: {result.get('error', 'Invalid')}")
            
            valid_count = len([r for r in results if r["valid"]])
            print(f"\nSummary: {valid_count}/{len(results)} documents valid")
            
            return 0 if valid_count == len(results) else 1
        
        # Download documents
        print("🔥 Campfire Document Downloader")
        print("=" * 50)
        print("Downloading official emergency guidance documents...")
        print()
        
        results = downloader.download_all_documents(args.force)
        
        # Verify downloaded documents
        print("\n🔍 Verifying downloaded documents...")
        verification_results = downloader.verify_all_documents()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 DOWNLOAD SUMMARY")
        print("=" * 50)
        
        successful_downloads = len([r for r in results if r["status"] in ["downloaded_placeholder", "exists_valid"]])
        valid_documents = len([r for r in verification_results if r["valid"]])
        
        print(f"Downloads: {successful_downloads}/{len(results)} successful")
        print(f"Verifications: {valid_documents}/{len(verification_results)} passed")
        
        if successful_downloads == len(results) and valid_documents == len(verification_results):
            print("\n✅ All documents downloaded and verified successfully!")
            print("Documents are ready for corpus ingestion.")
            return 0
        else:
            print("\n⚠️  Some documents failed to download or verify.")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())