# mood_analyzer.py
"""
Rule based mood analyzer for short text snippets.

This class starts with very simple logic:
  - Preprocess the text
  - Look for positive and negative words
  - Compute a numeric score
  - Convert that score into a mood label
"""

from typing import List, Dict, Tuple, Optional
import re
import string

from dataset import POSITIVE_WORDS, NEGATIVE_WORDS, SARCASM_PHRASES, SARCASM_EMOJIS


class MoodAnalyzer:
    """
    A very simple, rule based mood classifier.
    """

    def __init__(
        self,
        positive_words: Optional[List[str]] = None,
        negative_words: Optional[List[str]] = None,
        word_weights: Optional[Dict[str, int]] = None,
        sarcasm_phrases: Optional[List[str]] = None,
        sarcasm_emojis: Optional[List[str]] = None,
    ) -> None:
        # Use the default lists from dataset.py if none are provided.
        positive_words = positive_words if positive_words is not None else POSITIVE_WORDS
        negative_words = negative_words if negative_words is not None else NEGATIVE_WORDS

        # Store as sets for faster lookup.
        self.positive_words = set(w.lower() for w in positive_words)
        self.negative_words = set(w.lower() for w in negative_words)

        # Sarcasm indicators.
        self.sarcasm_phrases = [p.lower() for p in (sarcasm_phrases if sarcasm_phrases is not None else SARCASM_PHRASES)]
        self.sarcasm_emojis = set(sarcasm_emojis if sarcasm_emojis is not None else SARCASM_EMOJIS)

        # Word-specific weights (higher weight => stronger signal).
        # If not provided, use a small set of stronger words as defaults.
        default_weights: Dict[str, int] = {
            "love": 2,
            "hate": 2,
            "terrible": 2,
            "amazing": 2,
            "happy": 2,
            "sad": 2,
            "lol": 2,
        }
        provided = word_weights if word_weights is not None else {}
        # merge provided weights over defaults; normalize to lowercase
        merged: Dict[str, int] = {k.lower(): int(v) for k, v in default_weights.items()}
        for k, v in provided.items():
            merged[k.lower()] = int(v)

        self.word_weights = merged

    # ---------------------------------------------------------------------
    # Sarcasm detection
    # ---------------------------------------------------------------------

    def _is_sarcastic(self, text: str) -> bool:
        """
        Return True if the text contains a known sarcasm signal.

        Two checks are performed on the original (un-preprocessed) text:
          1. Phrase match — looks for entries in self.sarcasm_phrases.
          2. Emoji match  — looks for entries in self.sarcasm_emojis.
        """
        lower = text.lower()
        for phrase in self.sarcasm_phrases:
            if phrase in lower:
                return True
        for emoji in self.sarcasm_emojis:
            if emoji in text:
                return True
        return False

    # ---------------------------------------------------------------------
    # Preprocessing
    # ---------------------------------------------------------------------

    def preprocess(self, text: str) -> List[str]:
        """
        Convert raw text into a list of tokens the model can work with.

        TODO: Improve this method.

        Right now, it does the minimum:
          - Strips leading and trailing whitespace
          - Converts everything to lowercase
          - Splits on spaces

        Ideas to improve:
          - Remove punctuation
          - Handle simple emojis separately (":)", ":-(", "🥲", "😂")
          - Normalize repeated characters ("soooo" -> "soo")
        """
        cleaned = text.strip().lower()

        # Normalize repeated characters: 'soooo' -> 'soo'
        cleaned = re.sub(r'(.)\1{2,}', r'\1\1', cleaned)

        # Normalize common negation contractions to the token 'not'
        cleaned = re.sub(r"\b(can't|cant|don't|dont|didn't|didnt|won't|wont|n't)\b", "not", cleaned)

        # Separate emoji characters by surrounding them with spaces so they
        # become separate tokens. This covers common emoji Unicode ranges.
        emoji_pattern = re.compile(
          "["
          u"\U0001F600-\U0001F64F"
          u"\U0001F300-\U0001F5FF"
          u"\U0001F680-\U0001F6FF"
          u"\U0001F1E0-\U0001F1FF"
          "]+",
          flags=re.UNICODE,
        )
        cleaned = emoji_pattern.sub(lambda m: f" {m.group(0)} ", cleaned)

        # Remove punctuation (turn into spaces) so tokens like 'happy!' -> 'happy'
        # We already normalized contractions above, so it's safe to remove apostrophes.
        punct_map = {p: ' ' for p in string.punctuation}
        cleaned = cleaned.translate(str.maketrans(punct_map))

        # Split into tokens on whitespace
        tokens = cleaned.split()

        # Handle simple negation grouping: turn sequences like ['not', 'happy']
        # into single tokens 'neg_happy'. This makes it easier for scoring to
        # detect negated words.
        negation_words = {"not", "no", "never"}
        grouped_tokens: List[str] = []
        i = 0
        while i < len(tokens):
          tok = tokens[i]
          if tok in negation_words and i + 1 < len(tokens):
            next_tok = tokens[i + 1]
            grouped_tokens.append(f"neg_{next_tok}")
            i += 2
          else:
            grouped_tokens.append(tok)
            i += 1

        return grouped_tokens

    # ---------------------------------------------------------------------
    # Scoring logic
    # ---------------------------------------------------------------------

    def score_text(self, text: str) -> int:
        """
        Compute a numeric "mood score" for the given text.

        Positive words increase the score.
        Negative words decrease the score.
        """
        tokens = self.preprocess(text)

        score = 0

        # Loop over tokens and apply weights. Handle negation tokens produced
        # by `preprocess` which use the prefix 'neg_'. Default weight is 1.
        for token in tokens:
          # Negation handling: 'neg_happy' -> treat 'happy' with flipped sign
          if token.startswith("neg_"):
            base = token[4:]
            weight = self.word_weights.get(base, 1)
            if base in self.positive_words:
              score -= weight
            if base in self.negative_words:
              score += weight
            # if base isn't in either list, ignore
            continue

          # Regular token
          weight = self.word_weights.get(token, 1)
          if token in self.positive_words:
            score += weight
          if token in self.negative_words:
            score -= weight

        # If sarcasm is detected and the raw score looks positive/neutral,
        # flip it negative. -max(score, 2) ensures it crosses the -2 threshold
        # even when only one weak positive word was found (score == 1).
        if self._is_sarcastic(text) and score >= 0:
            score = -max(score, 2)

        return score

    # ---------------------------------------------------------------------
    # Label prediction
    # ---------------------------------------------------------------------

    def predict_label(self, text: str) -> str:
        """
        Turn the numeric score for a piece of text into a mood label.

        Mapping used here (with simple thresholds):
          - score >= 2  -> "positive"
          - score <= -2 -> "negative"
          - score == 0  -> "neutral"
          - otherwise    -> "mixed"

        "Mixed" is used for weak/ambiguous signals (score of -1 or 1).
        """
        score = self.score_text(text)

        if score >= 2:
            return "positive"
        if score <= -2:
            return "negative"
        if score == 0:
            return "neutral"
        return "mixed"

    # ---------------------------------------------------------------------
    # Explanations (optional but recommended)
    # ---------------------------------------------------------------------

    def explain(self, text: str) -> str:
        """
        Return a short string explaining WHY the model chose its label.
        """
        tokens = self.preprocess(text)

        positive_hits: List[str] = []
        negative_hits: List[str] = []
        score = 0

        for token in tokens:
          if token.startswith("neg_"):
            base = token[4:]
            w = self.word_weights.get(base, 1)
            if base in self.positive_words:
              negative_hits.append(f"neg_{base}(w={w})")
              score -= w
            if base in self.negative_words:
              positive_hits.append(f"neg_{base}(w={w})")
              score += w
            continue

          w = self.word_weights.get(token, 1)
          if token in self.positive_words:
            positive_hits.append(f"{token}(w={w})")
            score += w
          if token in self.negative_words:
            negative_hits.append(f"{token}(w={w})")
            score -= w

        sarcasm_note = ""
        if self._is_sarcastic(text) and score >= 0:
            score = -max(score, 2)
            sarcasm_note = ", sarcasm detected -> score flipped"

        return (
          f"Score = {score} "
          f"(positive: {positive_hits or '[]'}, "
          f"negative: {negative_hits or '[]'}"
          f"{sarcasm_note})"
        )