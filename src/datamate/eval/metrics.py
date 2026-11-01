from collections import Counter


def summarize(rows):
    counts = Counter(row['outcome'] for row in rows)
    answered = counts['correct'] + counts['wrong']
    total = len(rows)
    return {'total': total, 'correct': counts['correct'], 'wrong': counts['wrong'],
            'abstain': counts['abstain'], 'score': counts['correct'] - counts['wrong'],
            'coverage': answered / total if total else None,
            'selective_accuracy': counts['correct'] / answered if answered else None,
            'selective_risk': counts['wrong'] / answered if answered else None}
