# Gardener of the AI Era

A monsoon garden helper for South and Southeast Asia, built on open-weight models. It started as a sowing calendar (what should I plant this week?) and grew into one small app with six parts:

| Tab | What it does | Needs |
|---|---|---|
| **This week** | Which sowing season is open, what to start now, which window closes first. Optional note in your language, and a water-today tip | nothing (model optional; internet for the water tip) |
| **Plant check** | Photograph a sick leaf; Gemma lists possible causes and simple checks | a vision model (Gemma 3 4b or larger) |
| **Ask** | Ask in your own words; answers use only your place's calendar, with the real dates always shown | the model |
| **Seed packet** | Photograph a packet; Gemma reads it, the calendar decides whether to sow now | a vision model |
| **My garden** | Note what you planted; see when it's ready and when to sow another batch. Stays on your device | nothing |
| **Balcony** | Pots and hours of sun in, crops that fit out | nothing |

Almost every garden planner is built around frost dates. Most gardeners in India, Pakistan, Bangladesh, Sri Lanka and much of Southeast Asia never see a frost; their year runs on the monsoon. The calendar here is plain Python, computed from published monsoon and season dates. **The model never decides a date.** It writes, reads photos and answers questions, and every place it could invent something has a check.

Each tab is its own module in [`gardener/features/`](gardener/features/) with its own route, and can be switched off (`GARDENER_FEATURES=diary,water`, or `none` for just the calendar) without touching the rest.

Built for the Hacktoberfest Open-Source AI Challenge, Week 1: Touch Grass.

## The checks, feature by feature

| Feature | What could go wrong | What stops it |
|---|---|---|
| Weekly note | The model invents a crop or date | Every crop name (English or local, in eight languages) and date is checked against the plan; failures fall back to the built-in writer |
| Note in your language | The translation changes a date or isn't translated | Every number must survive unchanged (local digits like ३३ are understood), and the text must be in the target script; otherwise you get English and the reason |
| Plant check | A small model gives a confident wrong diagnosis or a spray dose | Answers are framed as possible causes with simple checks; any amount with ml, g, % and so on is removed and replaced with "ask a local nursery" |
| Ask | The model invents dates | Dates in the answer must be in the calendar it was given; crops must be in the calendar or the question. The engine's windows for any crop you name are always shown |
| Seed packet | The packet's printed months don't fit your place | Gemma only reads the packet; the decision ("sow now", "opens in 12 days") comes from your calendar |
| Water today | The forecast is down | Rules, not a model; if the forecast can't be reached, the app says so |

## Run it

No dependencies: Python 3.10+ and the standard library.

```bash
git clone <this repo> && cd gardener
python -m gardener serve            # http://localhost:8000
```

That already works, using the built-in writer. To get notes written by Gemma on your own machine, with no account and no internet after the download:

```bash
ollama pull gemma3:4b               # a few GB, once
python -m gardener serve            # finds Ollama on localhost:11434
```

Plant check and Seed packet need a model that can see images: Gemma 3 **4b** or larger (`gemma3:1b` is text-only).

On Windows PowerShell, set options like this before starting: `$env:GARDENER_TIMEOUT="120"`.

From the terminal:

```bash
python -m gardener card --region delhi
python -m gardener card --region colombo --date 2027-04-05
python -m gardener card --onset 06-10 --withdrawal 10-05            # your own monsoon dates
python -m gardener card --onset 06-01 --withdrawal 10-30 --no-cool-winter
python -m gardener regions
```

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GARDENER_LLM_URL` | `http://localhost:11434/v1` | Any OpenAI-compatible endpoint: Ollama, llama.cpp server, vLLM, a hosted provider |
| `GARDENER_MODEL` | `gemma3:4b` | The model name as that server knows it |
| `GARDENER_API_KEY` | none | Bearer token, for hosted endpoints |
| `GARDENER_LLM` | `on` | `off` skips the model and always uses the built-in writer |
| `GARDENER_TIMEOUT` | `45` | Seconds to wait for the model before falling back |
| `GARDENER_FEATURES` | `all` | Which optional tabs to switch on: `all`, `none`, or a list like `language,water,diary` |
| `PORT` / `HOST` | `8000` / `0.0.0.0` | Where the server listens |

## How the seasons work

Most of South Asia has one main monsoon, so a place is described by two dates people already know, **when the monsoon usually arrives and when it usually withdraws**, plus whether winters are cool enough for Rabi crops. Three sowing seasons follow from those dates:

| Season | Starts | Kind | Examples |
|---|---|---|---|
| Zaid / summer / Kharif-1 | 18 weeks before the monsoon (late February for Delhi) | hot and dry, needs watering | okra, gourds, cucumber, melons |
| Kharif / monsoon / Kharif-2 | when the monsoon arrives | warm and wet | okra, gourds, beans, amaranth, brinjal and chilli transplants, taro, ginger |
| Rabi / winter | when the monsoon withdraws | cool and dry | cauliflower, cabbage, peas, spinach, methi, carrot, onion, garlic, potato |

Places that don't follow that pattern list their seasons directly. Sri Lanka has **Yala** and **Maha**. Chennai has **Adi pattam** and **Thai pattam**, with the northeast monsoon from late October. The Southeast Asian presets use their weather services' **hot, rainy and cool** (or **wet and dry**) seasons. Each crop's window is a number of days before or after its season starts, kept in one readable file: [`gardener/crops.py`](gardener/crops.py). Crops show their local name for the place (bhindi, dherosh, bandakka, vendakkai, bendakaya, sitaw, rau muống...).

### Presets and where the dates come from

| Place | Dates | Source |
|---|---|---|
| New Delhi, Lucknow, Mumbai, Pune, Hyderabad, Kolkata | monsoon onset and withdrawal | IMD's new normal dates (2020) |
| Chennai | Adi pattam Jul 1, Thai pattam Jan 15; northeast monsoon from Oct 20 | TNAU season notes; IMD Chennai normal onset |
| Lahore | onset Jul 1, withdrawal Sep 30 | PMD normal onset (Jul 1). Sep 30 is the end of PMD's July–September season, not a published withdrawal normal |
| Dhaka | onset Jun 8, withdrawal Oct 8 | **Estimated**, midway between BMD's 1992–2021 means for the south-east and north-west. Not a published Dhaka normal |
| Colombo (wet zone), Anuradhapura (dry zone) | Yala Apr 1, Maha Sep 1 | Sri Lanka Department of Agriculture planting times; FAO for the monsoon months |
| Bangkok, Chiang Mai | hot season Feb 15, rainy May 15, cool Oct 15 | Thai Meteorological Department's national seasons. Chiang Mai gets Rabi-style crops because northern winters are cool; lowland Bangkok doesn't |
| Manila | wet season Jun 1, dry season Dec 1 | PAGASA: rainy season typically June to November |
| Ho Chi Minh City | rainy season May 1, dry season Dec 1 | Southern Vietnam's May–November rainy season (a month range, so the exact days are approximate) |

The crop offsets were checked against published sowing months, and the tests pin these checks:
- **Lahore, Punjab agriculture department:** summer vegetables in February–March, onion nursery until the end of November, transplanting in December–January.
- **Sri Lanka, Department of Agriculture:** okra in Yala from early April to early May, and in Maha from early September to early October.
- **Lowland Sri Lanka:** Gardener never suggests Rabi crops there.

Everything else is a rule of thumb for a home garden, from extension-service guidance. Your street, this year's rain, and your local agriculture office get the final say. For a town that isn't listed, choose **My own monsoon dates** and enter the dates your weather office publishes. Yangon, Jakarta, Hanoi and Phnom Penh aren't presets because I couldn't find published normals for them. Custom dates work there, including rains that cross New Year.

## The guardrail

`check_faithful` in [`gardener/brief.py`](gardener/brief.py) rejects any model reply that names a crop that isn't open or coming up, or a date that isn't in the facts the model was given. It recognizes English names, other English names (lady's finger, eggplant, kangkong) and local names in Hindi/Urdu, Bangla, Sinhala, Tamil, Telugu, Thai (romanized), Tagalog and Vietnamese. Longer names are matched first, so "water spinach" doesn't count as "spinach" and *makhuea thet* (tomato) doesn't count as *makhuea* (brinjal). A few local names that are also English words ("begun", Bangla for brinjal) are left out of the check. On rejection, the app shows the built-in note and says why. The page always says which writer produced the text.

## Privacy

Photos go only to the model endpoint you configure (your own laptop with Ollama, by default). The garden diary is kept in your browser's storage on your device. The water tip sends your city's coordinates to Open-Meteo, a free forecast service with no account.

## Works with no signal

The page is a small PWA. After one visit, a service worker keeps the app and your latest card, so it still opens in a field or on a rooftop with no reception, and says it's showing a saved copy. **Print this card** gives a clean one-pager for the wall by the garden tap.

## Deploy

| Where | Cost | What you get |
|---|---|---|
| **Render** ([`render.yaml`](render.yaml)) | Free plan (0.1 CPU, 512 MB) | The full app with the built-in writer. The free plan can't hold a model, so set `GARDENER_LLM=on` and `GARDENER_LLM_URL` to point at a model elsewhere. Free services sleep when idle, so the first request after a pause is slow |
| **DigitalOcean App Platform** ([`.do/app.yaml`](.do/app.yaml)) | Paid | The same container. Replace `YOUR_GITHUB_USER` first |
| **DigitalOcean GPU Droplet** | Paid, by the hour | A place to run Gemma yourself, with Ollama or vLLM. DigitalOcean's 1-Click Models serve an OpenAI-compatible vLLM endpoint, but Gemma wasn't on their documented list when this was written, so install Ollama or vLLM directly |
| **Anywhere with Docker** | n/a | `docker build -t gardener . && docker run -p 8000:8000 gardener` |

If you expose a model endpoint to the internet, put a key in front of it (`GARDENER_API_KEY`). A bare Ollama or vLLM port is open to anyone.

## Fine-tuning with Tinker

A general model has to be told to stay inside the facts. A small model tuned on engine-generated examples might do this one job more faithfully and more cheaply. The pipeline in [`training/`](training/) measures that instead of assuming it.

```bash
python training/make_dataset.py                    # 1,200 train + 150 held-out scenarios, no model needed
pip install -r training/requirements.txt
export TINKER_API_KEY=...                          # credits: hacktoberfest.com/my/promos
python training/train_tinker.py --list-models      # see what Tinker offers today
python training/train_tinker.py --dry-run          # check the data first, free
python training/train_tinker.py --base-model meta-llama/Llama-3.2-1B
```

Each example is a random gardener on a random day, either at a preset place or with random monsoon dates. The engine computes the facts, the prompt is exactly what the app sends, and the target is a correct note. The labels are right by construction, with no hand labeling and no second model. The script scores the **base model before tuning**, trains a LoRA, scores the **tuned model** on held-out scenarios, and prints a before/after table. The metrics are faithful notes, the three most urgent crops named, the right season named, and seconds per note.

To score Gemma, or any model you serve yourself:

```bash
python training/eval_faithfulness.py --model gemma3:4b --out training/results/gemma.json
```

Tinker's model list, when this was written, didn't include Gemma (it offered small Llama and Qwen models). So the comparison is **Gemma as the general-purpose baseline versus a small Tinker-tuned specialist**.

## Tests

```bash
python -m unittest discover -s tests
```

89 tests, standard library only. `tests/fake_model.py` is a stand-in OpenAI-compatible model that answers every kind of request (notes, translations, questions, plant and packet photos), with a `bad` mode that breaks every rule so the checks are exercised. They cover:
- **Season and date math:** year boundaries, leap day, rains that cross New Year, two rainy seasons, the pre-monsoon alert.
- **Published calendars:** spot checks against the sources above.
- **Fact-check property test:** the built-in writer always passes its own fact check across 1,600 random cases.
- **Local names:** fact-check cases for local names and overlapping names.
- **Model path:** tested against a stand-in OpenAI-compatible server (a good reply, a hallucinated one, an HTTP error, an unreachable server, a disabled model).
- **HTTP API:** including bad input.
- **Fine-tuning data:** the token shift and the loss masking.

## What has and hasn't been verified

Checked here:
- **Tests:** all 89 pass. Breaking the dose filter or the translation number check on purpose makes them fail. Breaking a calendar rule or the name matching on purpose makes them fail.
- **Browser:** the UI was rendered in a real browser at 390px and 320px wide and in dark mode, for Delhi, Colombo, Chennai, Dhaka, Ho Chi Minh City and custom dates. No horizontal overflow and no console errors.
- **Model path:** end to end over HTTP, against a **stand-in** model server.
- **Training scripts:** dataset generation, the `--dry-run`, and the reference evaluation.

- **Every tab clicked through in a real browser** at phone width with the stand-in model: plant check with a photo, ask, seed packet, diary (kept after reload), balcony, Hindi note.

**Not** checked, because it needs accounts, credits or hardware this was built without:
- **Real Gemma photo reading.** Plant check and Seed packet have only run against the stand-in. How often Gemma 3 4b reads a leaf or packet correctly is something to measure on real plants.
- **The water tip against the live forecast** (the build sandbox couldn't reach Open-Meteo). The request follows Open-Meteo's documented parameters.
- **Real Gemma output.** I have no latency or quality numbers yet. Measure them with `eval_faithfulness.py`.
- **A Tinker run.** The script follows the Tinker SDK docs but hasn't run against the live service.
- **Deployments.** The Render and DigitalOcean deploys haven't been done, and the Docker build hasn't run (no Docker daemon was available).
- **Local names.** These were written from general knowledge and checked by no native speaker. Corrections are welcome in `crops.py`.

## Limits

- **Averages:** season dates are averages. A monsoon can arrive two weeks early or late, and the app can't see the forecast.
- **Coverage:** fifteen preset places across seven countries. Equatorial places that are wet all year (Singapore, Kuala Lumpur) don't fit a two-date model well.
- **Highlands:** places like Ooty, Nuwara Eliya and Murree grow cool-season crops most of the year. They need their own calendar.
- **Crops:** 34 crops plus green manure and tree saplings. Pak choi is shown only for the Southeast Asian presets.

## License

No license file yet. Add one before publishing the repo (MIT is a common choice).
