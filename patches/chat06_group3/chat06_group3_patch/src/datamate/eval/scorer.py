def score(prediction, reference):
    if prediction['type'] == 'abstain':
        return 'abstain'
    if prediction['type'] != reference['type']:
        return 'wrong'
    if prediction['type'] in ('number', 'percent'):
        p, r = prediction.get('answer'), reference.get('answer')
        if type(p) not in (int, float) or type(r) not in (int, float):
            return 'wrong'
        return 'correct' if abs(p-r) <= 1e-9 * max(1, abs(r)) else 'wrong'
    return 'correct' if prediction.get('answer') == reference.get('answer') else 'wrong'
