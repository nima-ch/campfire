# Demo Preparation Guide
*For OpenAI Open Model Hackathon Presentation*

## Pre-Demo Setup Checklist

### System Configuration
- [ ] **Internet Disconnection**: Enable airplane mode or disconnect ethernet
- [ ] **Clean Environment**: Fresh browser session, clear terminal history
- [ ] **Backend Running**: Verify all services are operational offline
- [ ] **Corpus Loaded**: Confirm IFRC and WHO documents are indexed
- [ ] **Model Ready**: Ensure gpt-oss model is loaded and responsive

### Test Scenarios Prepared
- [ ] **Choking Emergency**: "Someone is choking and can't breathe"
- [ ] **Severe Bleeding**: "Deep cut on arm, bleeding heavily"  
- [ ] **Burns**: "Person burned by hot oil, skin is red and blistering"
- [ ] **Panic Attack**: "Someone having trouble breathing, very anxious"
- [ ] **Unconscious Person**: "Found someone unconscious, not responding"

### Demo Flow Verification
- [ ] **Query Input**: Test typing and submission
- [ ] **Response Generation**: Verify structured checklist appears
- [ ] **Citation Links**: Confirm all citations are clickable
- [ ] **Document Viewer**: Test snippet display and highlighting
- [ ] **Offline Indicator**: Verify "Offline" badge is visible
- [ ] **Admin Panel**: Test password access and audit logs

## Demo Script Walkthrough

### Opening (30 seconds)
**Setup**: Terminal window showing airplane mode enabled
**Action**: Navigate to http://localhost:8000
**Key Points**:
- Emphasize offline operation
- Show offline indicator in UI
- Mention emergency scenario context

### Core Demo (90 seconds)
**Scenario 1: Choking Emergency**
```
Query: "Someone is choking and can't breathe"
Expected Response: 
- Step-by-step Heimlich maneuver
- Citations to IFRC Guidelines
- Emergency services banner
- Clear action items
```

**Interaction Points**:
1. Type query slowly for visibility
2. Wait for response to generate completely
3. Click on first citation to show document viewer
4. Highlight the source text matching the guidance
5. Return to main interface

**Scenario 2: Psychological Support**
```
Query: "Person having panic attack after accident"
Expected Response:
- Psychological first aid steps
- Citations to WHO PFA Guide
- Calming techniques
- When to seek professional help
```

### Technical Showcase (45 seconds)
**Admin Panel Access**:
- Navigate to /admin
- Enter password
- Show Safety Critic logs
- Demonstrate audit trail

**Architecture Highlight**:
- Briefly show terminal with running processes
- Mention gpt-oss + Harmony integration
- Emphasize local-only operation

### Closing (15 seconds)
**Call to Action**:
- Show GitHub repository
- Mention one-command setup
- Highlight humanitarian impact

## Backup Plans

### If Demo Fails
**Option 1: Pre-recorded Footage**
- Have backup video of successful demo
- Screenshots of key features
- Architecture diagrams ready

**Option 2: Static Demonstration**
- Prepared response examples
- Citation screenshots
- Admin panel screenshots

**Option 3: Code Walkthrough**
- Show Harmony integration code
- Demonstrate Safety Critic logic
- Explain offline architecture

## Key Messages to Emphasize

### Technical Excellence (Best Local Agent)
1. **Harmony Integration**: "Uses gpt-oss with openai-harmony for structured tool calling"
2. **Multi-Hop Reasoning**: "Performs search → open → find sequences for precise citations"
3. **Safety Validation**: "Safety Critic component ensures response quality"
4. **Offline Architecture**: "Complete functionality without any internet dependency"

### Humanitarian Impact (For Humanity)
1. **Emergency Access**: "Works when internet fails in disasters"
2. **Authoritative Sources**: "Based on IFRC and WHO guidelines"
3. **Safety First**: "Built-in escalation for life-threatening situations"
4. **Universal Access**: "Runs on standard hardware, no cloud required"

## Technical Specifications to Mention

### gpt-oss Integration Details
- Model: gpt-oss-20b (or specific variant used)
- Framework: openai-harmony for tool orchestration
- Backends: vLLM (primary), Ollama (fallback), LM Studio (alternative)
- Tools: Custom "browser" tool for document search/retrieval

### Performance Metrics
- Response Time: <10 seconds typical
- Memory Usage: ~16GB RAM recommended
- Storage: ~10GB for models and corpus
- Offline Operation: 100% functionality without internet

### Safety Features
- Citation Enforcement: Every step requires source attribution
- Emergency Detection: Automatic escalation for critical keywords
- Scope Limitation: Responses limited to first-aid domain
- Medical Disclaimers: Clear warnings about professional medical advice

## Post-Demo Q&A Preparation

### Expected Questions

**Q: How does this compare to ChatGPT or other AI assistants?**
A: Unlike cloud-based assistants, Campfire works completely offline and provides cited, safety-validated responses from authoritative medical sources.

**Q: What happens if the model gives wrong advice?**
A: The Safety Critic component validates all responses, requires citations, and includes emergency escalation. All responses include medical disclaimers.

**Q: How do you ensure the information is up to date?**
A: We use the latest IFRC 2020 Guidelines and WHO 2011 PFA Guide. The system is designed for corpus updates when new guidelines are published.

**Q: Can this replace professional medical training?**
A: No - Campfire is for emergency preparedness and basic first aid. It always includes disclaimers and directs users to professional medical care.

**Q: How does the offline functionality work?**
A: Everything runs locally - gpt-oss models via vLLM/Ollama, SQLite database for documents, and React frontend. No external API calls.

### Demo Environment Checklist

#### Hardware Requirements
- [ ] Laptop with 16GB+ RAM
- [ ] GPU with 8GB+ VRAM (if using vLLM)
- [ ] Stable power connection
- [ ] Backup device ready

#### Software Setup
- [ ] All dependencies installed via uv
- [ ] Models downloaded and tested
- [ ] Corpus processed and indexed
- [ ] Frontend built and ready
- [ ] Docker containers ready (backup)

#### Network Configuration
- [ ] Airplane mode enabled OR ethernet disconnected
- [ ] WiFi disabled
- [ ] VPN disconnected
- [ ] Firewall configured to block external connections (optional verification)

#### Recording Setup
- [ ] Screen recording software configured
- [ ] Audio levels tested
- [ ] Backup recording device ready
- [ ] Upload method prepared for after demo

## Success Metrics

### Demo Objectives
1. **Functionality**: Show complete offline emergency guidance workflow
2. **Innovation**: Demonstrate gpt-oss + Harmony integration
3. **Safety**: Highlight citation system and Safety Critic
4. **Impact**: Convey humanitarian value and real-world applications
5. **Accessibility**: Show easy setup and broad hardware compatibility

### Audience Takeaways
- Campfire works completely offline for emergency situations
- Built with gpt-oss and Harmony for advanced local agent capabilities  
- Provides safety-validated guidance from authoritative medical sources
- Easy to install and run on standard hardware
- Addresses real humanitarian needs in disaster/remote scenarios

## Final Checklist Before Recording

### Technical Verification
- [ ] System running offline successfully
- [ ] All test scenarios work correctly
- [ ] Citations link to proper document sections
- [ ] Admin panel accessible and functional
- [ ] Performance is acceptable for demo

### Content Preparation
- [ ] Script memorized and timed
- [ ] Key talking points identified
- [ ] Backup plans ready
- [ ] Q&A responses prepared
- [ ] GitHub repository polished

### Recording Quality
- [ ] Screen resolution optimized
- [ ] Audio quality tested
- [ ] Lighting adequate for video
- [ ] Background noise minimized
- [ ] Recording software configured

**Target**: Under 3 minutes, professional quality, clear demonstration of offline emergency guidance capabilities with gpt-oss integration.