# বিজনেস রুল: স্কোর থেকে সিদ্ধান্ত। এখানে LLM নেই।
# মডেল শুধু স্কোর দেয় (prediction); নিচের থ্রেশহোল্ড ও পরামর্শ (recommendation) আলাদা পলিসি স্তর।
LOW, HIGH = 0.15, 0.30   # score < LOW → LOW | LOW ≤ score < HIGH → MEDIUM | score ≥ HIGH → HIGH

REASON_BN = {
    "amount_ratio": "অঙ্কটা আপনার সাধারণ লেনদেনের চেয়ে অনেক বেশি",
    "is_new_recipient": "এই নম্বরে আপনি আগে কখনো টাকা পাঠাননি",
    "hour": "লেনদেনের সময়টা অস্বাভাবিক",
    "tx_last_10min": "অল্প সময়ে অনেকগুলো লেনদেন হয়েছে",
    "just_received_money": "আপনি এইমাত্র টাকা পেয়েছেন এবং সাথে সাথে ফেরত পাঠাচ্ছেন",
    "amount": "অঙ্কটা বড়",
    "is_night": "রাতের লেনদেন",
}

# ফিচার → (সক্রিয় কি না, ইংরেজি কারণ, ছোট লেবেল)। মান আসে ইনপুট লেনদেন থেকে।
def _yn(v): return "Yes" if v else "No"

_RULES = {
    "amount_ratio": (lambda t: t["amount_ratio"] >= 2,
                     lambda t: f"Amount is {t['amount_ratio']:.1f}x the customer's usual transaction",
                     lambda t: f"Amount vs usual ({t['amount_ratio']:.1f}x)"),
    "is_new_recipient": (lambda t: t["is_new_recipient"] == 1,
                         lambda t: "First-time recipient",
                         lambda t: f"New recipient: {_yn(t['is_new_recipient'])}"),
    "hour": (lambda t: t["hour"] <= 5 or t["hour"] >= 22,
             lambda t: f"Unusual transaction time ({t['hour']:02d}:00)",
             lambda t: f"Hour of day ({t['hour']:02d}:00)"),
    "is_night": (lambda t: t["hour"] <= 5,
                 lambda t: "Late-night transaction (12am-5am)",
                 lambda t: f"Night-time: {_yn(0 <= t['hour'] <= 5)}"),
    "tx_last_10min": (lambda t: t["tx_last_10min"] >= 2,
                      lambda t: f"Recent unusual activity: {t['tx_last_10min']} transactions in 10 minutes",
                      lambda t: f"Transactions in last 10 min ({t['tx_last_10min']})"),
    "just_received_money": (lambda t: t["just_received_money"] == 1,
                            lambda t: "Money was just received and is being sent out right away",
                            lambda t: f"Just received money: {_yn(t['just_received_money'])}"),
    "amount": (lambda t: True,
               lambda t: f"Transaction amount (BDT {t['amount']:,.0f}) raised the risk score",
               lambda t: f"Amount (BDT {t['amount']:,.0f})"),
}

def feature_label(feature: str, tx: dict) -> str:
    return _RULES[feature][2](tx) if feature in _RULES else feature

def reason_texts(features: list, tx: dict) -> list:
    """SHAP-এ ঝুঁকি বাড়ানো ফিচারগুলো থেকে পাঠযোগ্য কারণ (মান বাস্তবে সক্রিয় হলে)।"""
    out = []
    for f in features:
        if f in _RULES and _RULES[f][0](tx):
            out.append(_RULES[f][1](tx))
    return out

ACTION_EN = {
    "LOW": "Transaction appears normal. You may proceed.",
    "MEDIUM": "Unusual pattern detected. Please review the recipient and amount before sending.",
    "HIGH": ("Additional verification recommended. Please verify the recipient before sending "
             "and never share your PIN or OTP. This transaction is flagged for analyst review."),
}
ACTION_BN = {
    "LOW": "লেনদেনটি স্বাভাবিক মনে হচ্ছে। আপনি এগিয়ে যেতে পারেন।",
    "MEDIUM": "কিছু অস্বাভাবিকতা পাওয়া গেছে। পাঠানোর আগে প্রাপক ও অঙ্ক আবার দেখে নিন।",
    "HIGH": ("অতিরিক্ত যাচাই প্রয়োজন। পাঠানোর আগে প্রাপককে যাচাই করুন এবং কাউকে PIN বা OTP দেবেন না। "
             "লেনদেনটি বিশ্লেষকের পর্যালোচনার জন্য চিহ্নিত হয়েছে।"),
}

def decide(score: float) -> dict:
    # `level`/`action`/`needs_human` পুরোনো কী, সামঞ্জস্যের জন্য রাখা হয়েছে।
    if score < LOW:
        lv, act, human = "LOW", "allow", False
    elif score < HIGH:
        lv, act, human = "MEDIUM", "review_before_sending", False
    else:
        lv, act, human = "HIGH", "additional_verification_and_review", True
    return {"level": lv.lower(), "risk_level": lv, "action": act,
            "recommended_action": ACTION_EN[lv], "recommended_action_bn": ACTION_BN[lv],
            "needs_human": human, "needs_human_review": human}

def template_message(level: str, reasons: list) -> str:
    # ব্যাকআপ বাংলা বার্তা (LLM ছাড়াই কাজ করে)। ব্যক্তিকে নয়, লেনদেনকে "ঝুঁকিপূর্ণ" বলা হয়।
    why = "; ".join(REASON_BN.get(r, r) for r in reasons)
    why = f" কারণ: {why}।" if why else ""
    level = level.lower()
    if level == "high":
        return f"এই লেনদেনটি উচ্চ ঝুঁকির হিসেবে চিহ্নিত হয়েছে, অতিরিক্ত যাচাই প্রয়োজন।{why} কাউকে PIN বা OTP দেবেন না।"
    if level == "medium":
        return f"একটু দেখে নিন।{why} নিশ্চিত হয়ে তারপর পাঠান।"
    return "লেনদেনটি স্বাভাবিক মনে হচ্ছে।"
