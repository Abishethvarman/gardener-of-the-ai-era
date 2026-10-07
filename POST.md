<!--
BEFORE YOU PUBLISH (delete this comment):
1. Fill in every [[double bracket]]. Nothing in brackets has been measured or experienced yet.
2. Use it outside and write "Taking it outside" yourself. It earns bonus points, and nobody else can write it.
3. Run training/train_tinker.py and training/eval_faithfulness.py, then paste your real numbers. If the tuned model doesn't win, say so. A clear honest result beats a flattering one.
4. Only keep the partner mentions you actually used. DEV allows 4 tags; ai and opensource sit alongside the two required ones.
5. If a local crop name is wrong for your language, fix it in crops.py before you post.
-->
---
title: Gardener of the AI Era: a monsoon garden helper for people who will never see a frost
published: false
tags: devchallenge, hf26challenge, ai, opensource
---

*This is my submission for the Hacktoberfest Open-Source AI Challenge: Week 1 ([[link to the challenge page]]), theme: Touch Grass.*

## What I built

Every garden planner I tried starts by asking for my frost dates. I don't have any. Neither do most gardeners in India, Pakistan, Bangladesh, Sri Lanka or most of Southeast Asia. Our year runs on the monsoon. (The word comes from the Arabic *mawsim*, "season", which is exactly what it is for us.)

**Gardener of the AI Era** started with one question, *what should I plant this week?*, and grew into a small garden helper with six tabs: the weekly sowing card, a plant photo check, questions in your own words, a seed packet reader, a garden diary and a balcony planner. The heart is still the calendar. You pick your city, or enter when your monsoon usually arrives and leaves. It tells you which sowing season is open, what to start now, which window closes first, and what's coming. In New Delhi on October 6, the note reads:

> Rabi sowing is open in New Delhi. Open this week: cauliflower nursery (phool gobhi), cabbage nursery (patta gobhi), tomato transplanting (tamatar), garlic (lehsun), mustard greens (sarson) and 8 more. Next up: cauliflower transplanting, opening in 3 days (Oct 9).

The same day in Colombo, it's Maha season and the okra (*bandakka*) window has a week left. In Dhaka the monsoon withdraws in two days and Rabi opens with it. In Chennai it warns that the northeast monsoon is two weeks out: raise the beds and clear the drains.

The page is meant to take thirty seconds on a phone. Then you put the phone away and go outside. Lots of us garden on rooftops and balconies, so every note ends with "Pick one bed or a few pots". After one visit the app works offline, and **Print this card** makes a one-pager for the wall by the garden tap.

[[Screenshot of the phone view for your city]]

## The calendar is code, not the model

The obvious build is to ask a model what to plant in Hyderabad in October. A wrong sowing date costs a gardener a season, and a small model is much better at sentences than at counting days. So Gardener splits the work:

- **A plain Python engine computes every date.** Most places are described by two dates people already know, monsoon onset and withdrawal, and the three seasons follow from them. Kharif starts with the rains. Rabi starts as they leave. Zaid starts eighteen weeks before the rains, which lands in late February for Delhi, the published time for summer vegetables. Sri Lanka's Yala and Maha and Chennai's Adi and Thai pattam are listed directly. Each crop's window is a number of days before or after its season starts.
- **The preset dates come from published normals:** IMD for six Indian cities, PMD's July 1 onset for Lahore, and the Sri Lanka Department of Agriculture's planting times. Dhaka is honestly labeled as an estimate between BMD's regional averages.
- **The model only phrases the result.** It gets the engine's facts as JSON and an instruction to use nothing else.

## Letting the model talk, and not trusting it

Every model reply goes through a fact check before anyone sees it. It rejects any reply that names a crop that isn't open, or a date that isn't in the plan. It knows crops by their English names and by local names in Hindi/Urdu, Bangla, Sinhala, Tamil, Telugu, Thai, Tagalog and Vietnamese. *Bhindi*, *dherosh*, *bandakka*, *vendakkai*, *bendakaya* and *đậu bắp* all count as okra.

```python
ok, problems = check_faithful(text, plan)
if not ok:
    return Brief(templated_brief(plan), "template", model=client.model,
                 note="The model's draft failed the fact check (...)")
```

Two details were harder than they looked. "Water spinach" isn't "spinach", so longer names are matched first. And *begun*, Bangla for brinjal, is also an English word, so "the season has begun" can't be allowed to trip the check.

The fallback is a deterministic writer that needs no model. A property test confirms it passes its own check across 1,600 random scenarios, so the fallback can never be the thing that breaks. The page always says which writer produced the text.

The check is a safety net for the most expensive mistake, not a proof of correctness. It doesn't verify every number in a sentence, and it can't judge whether advice is wise.

## Where Gemma does the real work

The calendar doesn't need a model. Everything around it does, and each feature has its own check:

- **Plant check.** Photograph a sick leaf and Gemma 3 (4b, which can see images) lists up to three possible causes, each with a simple thing to check. It never gives a diagnosis, and any spray or fertiliser amount is stripped out and replaced with "ask a local nursery". [[Your results: how many of your own plants did it get roughly right?]]
- **Note in your language.** Gemma translates the weekly note into Hindi, Bangla, Tamil, Telugu, Sinhala, Urdu, Thai, Vietnamese or Tagalog. Every number has to survive unchanged, and the text has to be in the right script, or you get the English note and the reason.
- **Ask.** "Can I still plant tomatoes on my terrace?" Gemma answers from your place's calendar only. Any date it writes must be in that calendar, and the engine's real dates for the crops you named are always shown underneath.
- **Seed packet.** Gemma reads the packet. Your calendar, not the packet, decides whether to sow now, because a packet printed for a whole country can't know your monsoon.

Two tabs use no model at all: **My garden** (harvest dates and "sow another batch" nudges, stored on your device) and **Balcony** (pots and hours of sun in, crops that fit out). Every tab is its own module and can be switched off without touching the rest.

## Why open mattered here

- **It runs on a laptop.** `ollama pull gemma3:4b`, then `python -m gardener serve`. [[Add your own measured numbers: laptop, time per note, RAM.]]
- **Swapping models is an environment variable.** The client speaks the OpenAI-compatible protocol, so Ollama, llama.cpp, vLLM and hosted endpoints are interchangeable.
- **It costs nothing to run.** Local inference is free, and the app itself fits on Render's free plan.
- **Your data stays put.** Photos of your garden go to a model on your own laptop, not a stranger's server, and your diary stays on your device.
- **You can build a specialist.** That's the next section, and a closed model wouldn't let you do it.

Where a closed model would have been easier: a hosted frontier model would likely write nicer prose with no setup, and might know more local names. The guardrail and the fallback are the price of a small model. I think the price is fair, because the app never depends on the model being right.

## Fine-tuning a specialist with Tinker

The training data costs nothing to label. Each example is a random gardener on a random day: the engine computes the facts, the prompt is exactly what the app sends, and the target is a correct note. The script scores the base model *before* tuning, trains a LoRA on [Tinker](https://tinker-docs.thinkingmachines.ai), and scores the tuned model on held-out scenarios.

[[Paste your real results. The script prints this table:]]

| | base model | tuned |
|---|---|---|
| faithful notes | [[ ]] | [[ ]] |
| names the 3 most urgent crops | [[ ]] | [[ ]] |
| names the right season | [[ ]] | [[ ]] |
| seconds per note | [[ ]] | [[ ]] |

Tinker's model list didn't include Gemma when I looked, so I compared Gemma as the general-purpose baseline against a small Tinker-tuned model. [[Add Gemma's numbers from eval_faithfulness.py and say which one you'd actually ship.]]

## Deploying it

The app is standard-library Python in a small container. [[Link: Render free deployment.]] On the free plan it runs with the built-in writer, because 512 MB can't hold a model. Point `GARDENER_LLM_URL` at a model elsewhere to get model-written notes. [[If you did it: describe running Gemma on a DigitalOcean GPU Droplet and what it cost.]]

## Taking it outside

[[Write this yourself, in 3–5 sentences. Where were you, and what did the card say for your city this week? What did you actually plant, in a bed, a grow bag or a pot? What did it get wrong, and how did it feel to have the screen be the shortest part of your evening? Be specific: "I sowed methi in two grow bags on my terrace on Saturday" beats any general line.]]

## Southeast Asia, and where I stopped

After South Asia, I added Bangkok and Chiang Mai (the Thai Meteorological Department's hot, rainy and cool seasons), Manila (PAGASA's June–November rainy season) and Ho Chi Minh City. I left out Yangon and Jakarta because I could only find year-by-year forecasts, not published normals, and I didn't want to invent them. The custom-dates option still works there, including Jakarta-style rains that run past New Year. Places that are wet all year, like Singapore and Kuala Lumpur, don't fit a two-date model, and I'd rather leave them out than pretend.

## Try it

- Demo: [[link]]
- Code: [[GitHub link]]
- Agent session: [[DevRelay link, optional]]

Built with plain Python, Gemma, [[Tinker]], [[Render]] and [[DigitalOcean]].
