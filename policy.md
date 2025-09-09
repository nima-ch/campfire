# Safety Critic Policy Configuration

This file defines the safety policies for the Campfire emergency helper system.

## Emergency Keywords

These keywords trigger emergency banners and escalation:

- `unconscious`, `unconsciousness`
- `not breathing`, `no pulse`
- `chest pain`, `heart attack`, `cardiac arrest`
- `stroke`, `brain attack`
- `severe bleeding`, `hemorrhage`
- `anaphylaxis`, `severe allergic reaction`
- `suicide`, `suicidal thoughts`
- `overdose`, `poisoning`
- `electric shock`, `electrocution`
- `choking`, `airway obstruction`
- `seizure`, `convulsion`
- `head injury`, `brain injury`
- `spinal injury`, `neck injury`
- `broken bone`, `fracture`
- `severe burn`, `third degree burn`
- `hypothermia`, `heat stroke`

## Blocked Phrases

These medical terms should not appear in responses:

- `diagnose`, `diagnosis`
- `prescribe`, `prescription`
- `medication`, `medicine`
- `drug`, `pharmaceutical`
- `surgery`, `surgical procedure`
- `operate`, `operation`
- `medical treatment`, `therapy`
- `cure`, `treatment plan`
- `disease`, `illness`
- `condition`, `disorder`
- `syndrome`, `pathology`

## Required Disclaimers

All responses must include:

- "Not medical advice"
- Reference to contacting emergency services
- Guidance to seek professional help

## Scope Guidelines

Content must stay within:

- First aid procedures
- Emergency preparedness
- Safety guidance
- Basic response actions
- Harm reduction

Content must NOT include:

- Medical diagnosis
- Treatment recommendations
- Medication advice
- Surgical procedures
- Clinical assessments