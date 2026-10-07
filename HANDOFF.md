# Gardener of the AI Era: project summary and handoff

Paste or attach this file at the start of a new conversation (with any Claude account) along with the project zip, and say: "Continue developing this project. Read HANDOFF.md first."

---

## 1. The pitch (for showcasing)

**Gardener of the AI Era** is a monsoon garden helper for South and Southeast Asia, built on open-weight AI that runs on a laptop.

Almost every garden planner asks for frost dates. Most gardeners in India, Pakistan, Bangladesh, Sri Lanka and much of Southeast Asia never see a frost. Their year runs on the monsoon: Kharif with the rains, Rabi after them, Zaid before, Yala and Maha in Sri Lanka. This app is built for that calendar.

It has six tabs:

| Tab | What it does | Uses the AI model? |
|---|---|---|
| This week | Which sowing season is open, what to plant now, what closes first. Note in your language. Water-today tip | Yes (note, translation). Watering uses a free forecast |
| Plant check | Photo of a sick leaf → possible causes and simple checks | Yes (vision) |
| Ask | Question in your own words → answer from your calendar, with real dates shown | Yes |
| Seed packet | Photo of a packet → "sow now" or "opens in N days" for your place | Yes (vision reads the packet; the calendar decides) |
| My garden | Diary of plantings → harvest dates, "sow another batch" nudges. Stored on the device | No |
| Balcony | Pots + hours of sun → crops that fit this week | No |

**Core idea: the model never decides a date.** A plain Python engine computes the calendar from published monsoon dates. Gemma writes, translates, reads photos and answers questions, and every place it could invent something has a check (see section 4).

**Why open AI matters here:** runs on a laptop with no internet (Ollama + Gemma), garden photos stay on your own machine, costs nothing to run, works in local languages, and models can be swapped or fine-tuned.

Built for the **Hacktoberfest Open-Source AI Challenge, Week 1: "Touch Grass"** on DEV. **Submission deadline: October 11, 2026.** Prizes targeted: overall, Best Use of Gemma, Best Use of Render, Best Use of Tinker (DigitalOcean optional; it costs money).

---

## 2. Current status (as of October 7, 2026)

**Done and verified**
- **Tests:** all 89 pass (`python -m unittest discover -s tests`). Deliberately breaking a guard makes them fail.
- **Browser:** every tab was clicked through at phone width with a stand-in model. It works in dark mode, has no horizontal scrolling and logs no console errors.
- **Offline:** with the server stopped, the page shows the last saved card.
- **Real Gemma on the owner's laptop (Windows, Ollama, `gemma3:4b`):** the text path works, with a test reply in about 3.3 seconds.

**Not yet done or verified**
- **Photo tabs with real Gemma:** Plant check and Seed packet have only run against the stand-in model. Test them with `gemma3:4b` and real photos, and record how often they're right.
- **Water tip with the live forecast:** the build sandbox couldn't reach Open-Meteo, so this needs testing on a machine with internet.
- **GitHub:** no repository yet.
- **Render:** not deployed. The config `render.yaml` is ready, and on the free plan the app runs without a model.
- **Tinker:** no fine-tuning run yet. The script follows the Tinker docs and its dry run passes.
- **The DEV post (`POST.md`):** it has 17 `[[bracket]]` placeholders the owner must fill. That includes real timings, real photo results, the demo link and the "Taking it outside" story, which is personal and earns bonus points.
- **Local crop names:** these are unchecked by native speakers.
- **Owner's city:** not yet chosen. The default is New Delhi.

**Earlier versions, kept separately**
- **Frostline:** the first frost-date version, now superseded.
- **Rainline:** the calendar only. Gardener is Rainline plus the features.

---

## 3. How to run

```bash
python -m gardener serve                 # http://localhost:8000, no dependencies (Python 3.10+)
ollama pull gemma3:4b                    # for model features; 4b or larger needed for photos
python -m gardener card --region delhi   # terminal version
python -m unittest discover -s tests     # tests
python tests/fake_model.py 8299          # stand-in model for testing ("bad" as 2nd arg breaks rules)
```

Environment variables (on Windows PowerShell use `$env:NAME="value"`):

| Variable | Default | Meaning |
|---|---|---|
| `GARDENER_LLM_URL` | `http://localhost:11434/v1` | Any OpenAI-compatible endpoint |
| `GARDENER_MODEL` | `gemma3:4b` | Model name |
| `GARDENER_API_KEY` | none | For hosted endpoints |
| `GARDENER_LLM` | `on` | `off` = built-in writer only |
| `GARDENER_TIMEOUT` | `45` | Seconds (use 120 on slow laptops) |
| `GARDENER_FEATURES` | `all` | `none`, or e.g. `language,water,diary` |

---

## 4. Architecture

Standard-library Python only. No frameworks, no pip installs for the app.

```
gardener/
  engine.py      sowing calendar: seasons, windows, rains, alerts (no model)
  regions.py     15 preset places + custom monsoon dates; sources in the docstring
  crops.py       34 crops: windows per season kind, local names (9 languages),
                 days to harvest, sun need, pot size
  brief.py       weekly note: built-in writer + model writer + fact check
  llm.py         tiny OpenAI-compatible client (text + images + JSON mode)
  service.py     request parsing, plan JSON, caching, translation hook
  server.py      HTTP routes (GET + POST JSON), feature on/off
  cli.py         terminal commands
  features/      one module per optional feature:
    language.py  translation; check: numbers preserved + correct script
    water.py     Open-Meteo forecast + plain rules
    photo.py     plant check; check: JSON only, doses stripped
    ask.py       Q&A; check: dates must be in the calendar given
    packet.py    seed packet reader; calendar decides, not the packet
    diary.py     harvest dates and resow nudges (no model)
    balcony.py   pot and sun filter (no model)
  static/        index.html (whole UI, vanilla JS), sw.js (offline), manifest, icon
tests/           89 tests + fake_model.py
training/        Tinker fine-tuning: make_dataset.py, train_tinker.py, eval_faithfulness.py
render.yaml, .do/app.yaml, Dockerfile
README.md, POST.md (DEV post draft), HANDOFF.md (this file)
```

**The calendar model:**
- **Most places:** two dates describe the place, monsoon onset and withdrawal, plus whether winters are cool. The sowing seasons follow from those:
  - dry (Zaid): onset minus 126 days
  - wet (Kharif): onset
  - cool (Rabi): withdrawal
- **Places with explicit seasons:** Sri Lanka (Yala Apr 1, Maha Sep 1), Chennai (Adi and Thai pattam), Bangkok and Chiang Mai, Manila and Ho Chi Minh City list their seasons directly.
- **Crop windows:** each is a number of days relative to its season's start.

**Date sources:** IMD 2020 normals (Indian cities), PMD (Lahore onset July 1), BMD ranges (Dhaka is an estimate between them), Sri Lanka Department of Agriculture, TNAU, IMD Chennai (northeast monsoon from Oct 20), Thai Meteorological Department, PAGASA.

**Places left out on purpose:** Yangon, Jakarta, Hanoi and Phnom Penh have no published normals I could find, so they need custom dates. Singapore and Kuala Lumpur are wet all year, so a two-date model doesn't fit.

**Rules the code follows (keep them):**
- **Dates come from code.** The model never produces a date the engine didn't compute.
- **Model replies are checked.** Every model output passes a check or falls back to something honest, and the UI says which happened.
- **Each feature is isolated.** It has its own module and route, can be switched off, and has tests that use the stand-in model.
- **Unverified things are labeled.** Estimates and untested features say so in the app, README and post.

---

## 5. Next steps, in priority order

1. **Owner's city:** set it as the default (`DEFAULT_REGION` in `regions.py`) and redo the screenshots.
2. **Real Gemma tests:** on the owner's laptop, run the photo tabs and the translation with real plants and packets, and note timings and accuracy for the post.
3. **GitHub:** push to a repository, and add a LICENSE (MIT suggested).
4. **Render:** deploy with New, then Blueprint, which uses `render.yaml`. Get credits at hacktoberfest.com/my/promos.
5. **Touch grass:** plant something the app suggests, take a photo, and write the "Taking it outside" section.
6. **Post:** fill every `[[bracket]]` in `POST.md`, add screenshots, and publish on DEV before **October 11** with the tags `devchallenge` and `hf26challenge`.
7. **Optional, Tinker:** claim credits, run `training/train_tinker.py`, and paste the before/after table. Skip it if time is short, because the post matters more.

**Ideas after the challenge:**
- **Live rain:** use this year's actual monsoon onset instead of averages.
- **Local names:** have native speakers check them.
- **More places:** Nepal, Myanmar and Indonesia, if normals can be found.
- **Highland calendars:** Ooty, Nuwara Eliya and Murree, which grow cool crops most of the year.
- **Voice:** a voice note in the local language.
- **Diary sync:** across devices, optionally.

---

## 6. Notes for the next Claude

- **The owner's English is limited.** Use short, simple sentences and numbered steps, and explain what each output means.
- **The owner works on Windows with Anaconda PowerShell.** Give PowerShell syntax (`$env:X="y"`), not `set X=y` or bash.
- **Development happens on the owner's laptop** at a path like `D:\Research\Hacktoberfest\...`. Changes made in a cloud sandbox reach it only as files the owner downloads.
- **Earlier model errors:** the app hit HTTP 404 and 500 errors from Ollama because the model wasn't downloaded yet. `ollama run gemma3:4b "hello"` fixed it.
- **Before changing code,** run the tests. After changing code, run them again.
