# Campfire Demo Video Script
*Target: Under 3 minutes for OpenAI Open Model Hackathon*

## Opening Hook (0:00-0:15)
**[Screen: Terminal showing airplane mode enabled]**

"Imagine you're camping in a remote area with no cell service. Someone gets injured, and you need emergency guidance. This is Campfire - an offline emergency helper that works when the internet doesn't."

**[Screen: Show offline indicator in browser]**

## Problem Statement (0:15-0:30)
**[Screen: News headlines about natural disasters, remote emergencies]**

"In emergencies, internet connectivity often fails exactly when you need help most. Traditional AI assistants require cloud connections and can't guarantee safety-critical accuracy."

## Solution Overview (0:30-0:45)
**[Screen: Campfire interface loading]**

"Campfire solves this with gpt-oss running completely offline, using Harmony tools to search authoritative medical sources - IFRC 2020 Guidelines and WHO Psychological First Aid."

**[Screen: Show IFRC and WHO logos/documents]**

## Live Demo - Emergency Scenario (0:45-1:30)
**[Screen: Campfire chat interface]**

**Type query:** "Someone is choking and can't breathe"

**[Show response appearing with step cards]**

"Watch how Campfire provides a structured checklist with precise citations. Each step links directly to the source document."

**[Click on citation, show document viewer]**

"Every recommendation is backed by authoritative sources. The Safety Critic ensures responses stay within scope and include proper medical disclaimers."

**[Show emergency banner: "Not medical advice. Call emergency services."]**

## Technical Innovation (1:30-2:00)
**[Screen: Architecture diagram or code snippets]**

"Under the hood, Campfire demonstrates advanced gpt-oss capabilities:
- Harmony orchestration for multi-step tool calling
- Local document search with FTS5 indexing  
- Safety-critical response validation
- Complete offline operation"

**[Screen: Show tool loop: search → open → find → synthesize]**

## Hackathon Categories (2:00-2:30)
**[Screen: Split showing "Best Local Agent" and "For Humanity"]**

**Best Local Agent:**
"Campfire showcases sophisticated local reasoning - multi-hop document retrieval, structured output generation, and safety validation - all without cloud dependencies."

**For Humanity:**
"More importantly, it addresses real humanitarian needs. Emergency responders, remote communities, and disaster zones can access life-saving guidance when connectivity fails."

## Call to Action (2:30-2:45)
**[Screen: GitHub repository, installation commands]**

"Try Campfire yourself - one command setup with uv, works with vLLM, Ollama, or LM Studio. The code is open source and ready for your emergency preparedness needs."

**[Screen: Terminal showing: `make setup && make ingest && make run`]**

## Closing (2:45-3:00)
**[Screen: Campfire logo with tagline]**

"Campfire: Emergency guidance that works when nothing else does. Built with gpt-oss for the OpenAI Open Model Hackathon."

**[Screen: GitHub URL and "For Humanity" badge]**

---

## Demo Checklist

### Pre-Recording Setup
- [ ] Enable airplane mode/disconnect internet
- [ ] Clear browser cache and history
- [ ] Prepare test scenarios:
  - "Someone is choking"
  - "Severe bleeding from cut"
  - "Person having panic attack"
- [ ] Test all citation links work
- [ ] Verify offline indicator shows
- [ ] Check admin panel access

### Recording Equipment
- [ ] Screen recording software (OBS/QuickTime)
- [ ] Good microphone for clear narration
- [ ] Stable internet for upload (after recording)
- [ ] Backup recording device

### Post-Production
- [ ] Edit to under 3 minutes
- [ ] Add captions for accessibility
- [ ] Include GitHub URL overlay
- [ ] Export in high quality (1080p minimum)
- [ ] Test playback on different devices

### Key Messages to Emphasize
1. **Offline-first** - Works without internet
2. **Safety-critical** - Authoritative sources with citations
3. **gpt-oss innovation** - Advanced local agent capabilities
4. **Humanitarian impact** - Real-world emergency applications
5. **Easy setup** - One-command installation with uv

### Backup Scenarios
If live demo fails:
- Pre-recorded demo footage
- Screenshots of key features
- Architecture diagrams
- Code snippets showing Harmony integration

### Timing Breakdown
- Hook: 15 seconds
- Problem: 15 seconds  
- Solution: 15 seconds
- Demo: 45 seconds
- Technical: 30 seconds
- Categories: 30 seconds
- CTA: 15 seconds
- Close: 15 seconds
- **Total: 3:00 minutes**