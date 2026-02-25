from mood_analyzer import MoodAnalyzer

samples = [
    "I love this! It's amazing :)",
    "I hate this. It's terrible.",
    "I'm not happy with this",
    "soooo happy lol",
    "This is okay, not bad",
    "I am sad"
]

ma = MoodAnalyzer()

for s in samples:
    score = ma.score_text(s)
    label = ma.predict_label(s)
    explanation = ma.explain(s)
    print(f"Text: {s}")
    print(f"  Score: {score} | Label: {label}")
    print(f"  Explanation: {explanation}\n")
