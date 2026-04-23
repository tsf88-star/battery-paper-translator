# -*- coding: utf-8 -*-
import re
import sys
import collections

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CORPUS_PATH = r"C:\Users\cho_b\Documents\이&최 습식 실리콘 논문\merged_corpus.txt"

# ── helpers ──────────────────────────────────────────────────────────────────

def split_sentences(text):
    """Rough sentence splitter (handles abbreviations like e.g., et al., Fig.)"""
    text = re.sub(r"\s+", " ", text)
    # protect common abbreviations
    for abbr in ["e.g.", "i.e.", "et al.", "Fig.", "Eq.", "vs.", "ca.", "approx.",
                 "cf.", "ref.", "Ref.", "vol.", "no.", "pp.", "al."]:
        text = text.replace(abbr, abbr.replace(".", "@@"))
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.replace("@@", ".").strip() for s in sents if len(s.split()) > 3]

def is_passive(sentence):
    """Heuristic: contains 'was/were/is/are/been + past-participle'"""
    return bool(re.search(
        r"\b(was|were|is|are|been|be|being)\s+\w+ed\b", sentence, re.IGNORECASE
    ))

def word_count(sentence):
    return len(sentence.split())

# ── load corpus ───────────────────────────────────────────────────────────────

with open(CORPUS_PATH, encoding="utf-8") as f:
    raw = f.read()

# Split by paper
papers = re.split(r"={40,}\n\[SOURCE:.*?\]\n={40,}", raw)
papers = [p.strip() for p in papers if len(p.strip()) > 200]

print(f"Total papers parsed: {len(papers)}\n")

# ── 1. SENTENCE STRUCTURE ─────────────────────────────────────────────────────

all_sents = []
passive_count = 0
for paper in papers:
    sents = split_sentences(paper)
    all_sents.extend(sents)
    for s in sents:
        if is_passive(s):
            passive_count += 1

total = len(all_sents)
avg_len = sum(word_count(s) for s in all_sents) / total if total else 0
passive_pct = 100 * passive_count / total if total else 0

print("=== 1. SENTENCE STRUCTURE ===")
print(f"  Total sentences analysed : {total:,}")
print(f"  Average sentence length  : {avg_len:.1f} words")
print(f"  Passive constructions    : {passive_count:,} / {total:,}  ({passive_pct:.1f}%)")

# ── 2. INTRO / CONCLUSION PATTERNS ───────────────────────────────────────────

INTRO_TRANSITION = [
    "recently", "in recent years", "over the past", "it has been", "has been reported",
    "has attracted", "have attracted", "considerable attention", "great attention",
    "significant attention", "is one of", "are one of", "among the", "however",
    "nevertheless", "despite", "although", "unfortunately", "to address",
    "to overcome", "to solve", "to tackle", "in this work", "in this study",
    "herein", "in this paper", "this work", "this study", "we report", "we propose",
    "we demonstrate", "we present", "we develop", "we investigate",
]

CONCL_TRANSITION = [
    "in conclusion", "in summary", "in this work", "to summarize", "overall",
    "collectively", "taken together", "the results demonstrate", "the results show",
    "the results indicate", "it was demonstrated", "it was shown", "it was found",
    "it is concluded", "these results", "this work", "this study", "we have",
    "we successfully", "we demonstrated", "we developed", "we proposed",
    "furthermore", "moreover", "in addition", "importantly", "notably",
    "this provides", "this offers", "paving the way", "opens a new",
]

intro_counts = collections.Counter()
concl_counts = collections.Counter()

for paper in papers:
    lines = paper.split("\n")
    # Take first 25% as "intro zone", last 20% as "conclusion zone"
    n = len(lines)
    intro_zone = " ".join(lines[:max(1, n//4)]).lower()
    concl_zone = " ".join(lines[max(0, int(n*0.80)):]).lower()

    for phrase in INTRO_TRANSITION:
        c = intro_zone.count(phrase.lower())
        if c:
            intro_counts[phrase] += c
    for phrase in CONCL_TRANSITION:
        c = concl_zone.count(phrase.lower())
        if c:
            concl_counts[phrase] += c

print("\n=== 2. INTRO TRANSITION WORDS (top 20) ===")
for phrase, cnt in intro_counts.most_common(20):
    print(f"  {cnt:3d}x  '{phrase}'")

print("\n=== 2. CONCLUSION TRANSITION WORDS (top 20) ===")
for phrase, cnt in concl_counts.most_common(20):
    print(f"  {cnt:3d}x  '{phrase}'")

# ── 3. ELECTROCHEMICAL TERMINOLOGY ──────────────────────────────────────────

VERBS = [
    "exhibit", "exhibits", "exhibited", "demonstrate", "demonstrates", "demonstrated",
    "show", "shows", "showed", "achieve", "achieves", "achieved",
    "deliver", "delivers", "delivered", "maintain", "maintains", "maintained",
    "retain", "retains", "retained", "improve", "improves", "improved",
    "enhance", "enhances", "enhanced", "increase", "increases", "increased",
    "decrease", "decreases", "decreased", "reduce", "reduces", "reduced",
    "suppress", "suppresses", "suppressed", "stabilize", "stabilizes", "stabilized",
    "attribute", "attributed", "degrade", "degrades", "degraded",
    "deteriorate", "deteriorates", "deteriorated", "fail", "fails", "failed",
    "result in", "results in", "lead to", "leads to",
    "contribute to", "contributes to",
    "arise from", "arises from", "stem from",
]

NOUNS = [
    "capacity retention", "coulombic efficiency", "initial coulombic efficiency",
    "cycle stability", "cycling stability", "rate capability", "rate performance",
    "volumetric expansion", "volume expansion", "volume change",
    "capacity fade", "capacity loss", "capacity decay",
    "solid electrolyte interphase", "sei", "sei layer", "sei film",
    "charge transfer resistance", "impedance", "eis",
    "lithiation", "delithiation", "intercalation", "deintercalation",
    "pulverization", "cracking", "fracture", "agglomeration",
    "conductivity", "ionic conductivity", "electronic conductivity",
    "diffusion coefficient", "lithium ion diffusion",
    "binder", "current collector", "active material",
    "silicon anode", "si anode", "graphite anode", "composite anode",
    "specific capacity", "gravimetric capacity", "areal capacity",
    "energy density", "power density",
    "electrolyte", "separator", "cathode", "anode",
]

corpus_lower = raw.lower()

print("\n=== 3a. VERB FREQUENCY ===")
verb_counts = {}
for v in VERBS:
    c = len(re.findall(r"\b" + re.escape(v) + r"\b", corpus_lower))
    if c:
        verb_counts[v] = c
for v, c in sorted(verb_counts.items(), key=lambda x: -x[1])[:30]:
    print(f"  {c:4d}x  {v}")

print("\n=== 3b. NOUN/PHRASE FREQUENCY ===")
noun_counts = {}
for n in NOUNS:
    c = corpus_lower.count(n.lower())
    if c:
        noun_counts[n] = c
for n, c in sorted(noun_counts.items(), key=lambda x: -x[1])[:30]:
    print(f"  {c:4d}x  {n}")

# ── 4. VERB + NOUN COLLOCATIONS ───────────────────────────────────────────────
KEY_VERBS   = ["exhibit", "demonstrate", "show", "achieve", "deliver",
               "maintain", "retain", "improve", "enhance", "suppress",
               "attribute", "degrade", "deteriorate"]
KEY_NOUNS   = ["capacity", "efficiency", "stability", "retention", "expansion",
               "resistance", "conductivity", "performance", "impedance", "sei"]

print("\n=== 4. TOP VERB–NOUN COLLOCATIONS ===")
collocations = collections.Counter()
for sent in all_sents:
    sl = sent.lower()
    for v in KEY_VERBS:
        if re.search(r"\b" + v, sl):
            for n in KEY_NOUNS:
                if n in sl:
                    collocations[(v, n)] += 1

for (v, n), c in collocations.most_common(25):
    print(f"  {c:3d}x  '{v}' + '{n}'")

# ── 5. degraded vs deteriorated ───────────────────────────────────────────────
print("\n=== 5. DEGRADE vs DETERIORATE ===")
for word in ["degrad", "deteriorat", "decay", "fade", "fail"]:
    c = len(re.findall(r"\b" + word + r"\w*\b", corpus_lower))
    print(f"  {c:4d}x  {word}*")

# ── 6. PASSIVE SENTENCE SAMPLES ───────────────────────────────────────────────
print("\n=== 6. SAMPLE PASSIVE SENTENCES ===")
passive_samples = [s for s in all_sents if is_passive(s) and 10 < word_count(s) < 30][:8]
for s in passive_samples:
    print(f"  > {s}")

print("\n=== 7. SAMPLE ACTIVE SENTENCES ===")
active_samples = [s for s in all_sents if not is_passive(s) and 10 < word_count(s) < 25][:8]
for s in active_samples:
    print(f"  > {s}")
