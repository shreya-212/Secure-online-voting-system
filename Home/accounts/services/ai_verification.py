"""
AI Genuineness Verification Service
=====================================
Rule-based scoring engine that analyses a voter registration request and returns:
  - ai_score   : int 0-100  (higher = more genuine)
  - ai_details : dict with per-check breakdown and messages

No external API is required — all checks are local pattern/logic validation.
"""

import re
from datetime import date, datetime


# ──────────────────────────────────────────────────────────────────────────────
# Helper validators
# ──────────────────────────────────────────────────────────────────────────────

def _check_voter_id(voter_id: str) -> dict:
    """
    Indian Voter ID (EPIC) format: 3 uppercase letters followed by 7 digits.
    Examples: ABC1234567, XYZ0009876
    """
    vid = (voter_id or "").strip().upper()
    points = 0
    messages = []

    if not vid:
        messages.append("❌ Voter ID is missing.")
        return {"points": 0, "max": 25, "messages": messages}

    # Standard EPIC format
    if re.fullmatch(r'[A-Z]{3}[0-9]{7}', vid):
        points = 25
        messages.append("✅ Voter ID format is valid (EPIC standard).")
    elif re.fullmatch(r'[A-Z]{2,4}[0-9]{5,8}', vid):
        # Partial match — uncommon but possible in some states
        points = 15
        messages.append("⚠️ Voter ID format is non-standard but plausible.")
    else:
        points = 0
        messages.append("❌ Voter ID format is invalid. Expected format: ABC1234567.")

    # Duplicate character suspicion (e.g., AAAAAA0000000)
    if len(set(vid[:3])) == 1:
        points = max(0, points - 10)
        messages.append("⚠️ Suspicious: all prefix letters are identical.")

    return {"points": points, "max": 25, "messages": messages}


def _check_aadhaar(aadhaar_last4: str) -> dict:
    """
    We only store the last 4 digits of Aadhaar.
    Validate they are exactly 4 numeric digits.
    """
    a4 = (aadhaar_last4 or "").strip()
    messages = []

    if not a4:
        messages.append("❌ Aadhaar last 4 digits are missing.")
        return {"points": 0, "max": 20, "messages": messages}

    if re.fullmatch(r'[0-9]{4}', a4):
        if a4 in ('0000', '1111', '2222', '3333', '4444', '5555',
                  '6666', '7777', '8888', '9999', '1234', '0000'):
            messages.append("⚠️ Aadhaar digits look like a repeated/sequential pattern — may be fake.")
            return {"points": 10, "max": 20, "messages": messages}
        messages.append("✅ Aadhaar last 4 digits are valid numeric digits.")
        return {"points": 20, "max": 20, "messages": messages}
    else:
        messages.append("❌ Aadhaar last 4 must be exactly 4 numeric digits.")
        return {"points": 0, "max": 20, "messages": messages}


def _check_age(date_of_birth: str) -> dict:
    """
    Voter must be at least 18 years old.
    Accepts: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
    """
    dob_str = (date_of_birth or "").strip()
    messages = []

    if not dob_str:
        messages.append("⚠️ Date of birth not provided.")
        return {"points": 5, "max": 15, "messages": messages}

    dob = None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %m %Y'):
        try:
            dob = datetime.strptime(dob_str, fmt).date()
            break
        except ValueError:
            continue

    if dob is None:
        messages.append("⚠️ Date of birth format could not be parsed.")
        return {"points": 5, "max": 15, "messages": messages}

    today = date.today()
    age = (today - dob).days // 365

    if age < 0 or dob > today:
        messages.append("❌ Date of birth is in the future.")
        return {"points": 0, "max": 15, "messages": messages}

    if age < 18:
        messages.append(f"❌ Age is {age} years — must be at least 18 to register.")
        return {"points": 0, "max": 15, "messages": messages}

    if age > 120:
        messages.append("❌ Age exceeds plausible range (>120 years).")
        return {"points": 0, "max": 15, "messages": messages}

    messages.append(f"✅ Age is {age} years — eligible to vote.")
    return {"points": 15, "max": 15, "messages": messages}


def _check_name(full_name: str) -> dict:
    """
    Name should be at least 3 chars, contain only letters and spaces,
    and not be all same characters.
    """
    name = (full_name or "").strip()
    messages = []

    if not name:
        messages.append("❌ Full name is missing.")
        return {"points": 0, "max": 15, "messages": messages}

    if len(name) < 3:
        messages.append("❌ Name is too short (minimum 3 characters).")
        return {"points": 3, "max": 15, "messages": messages}

    if not re.match(r"^[A-Za-z\s\.\-']+$", name):
        messages.append("⚠️ Name contains unusual characters (digits or symbols).")
        return {"points": 8, "max": 15, "messages": messages}

    # Suspicion: all same word repeated (e.g., "test test test")
    words = name.split()
    if len(words) > 1 and len(set(w.lower() for w in words)) == 1:
        messages.append("⚠️ Suspicious: name appears to be the same word repeated.")
        return {"points": 5, "max": 15, "messages": messages}

    # Suspicion: very generic test names
    generic = {'test', 'asdf', 'qwerty', 'lorem', 'ipsum', 'admin', 'user', 'unknown', 'anonymous'}
    if any(w.lower() in generic for w in words):
        messages.append("⚠️ Suspicious: name looks like a placeholder/test value.")
        return {"points": 3, "max": 15, "messages": messages}

    messages.append("✅ Name appears valid.")
    return {"points": 15, "max": 15, "messages": messages}


def _check_email(email: str) -> dict:
    """Standard email format validation."""
    em = (email or "").strip().lower()
    messages = []

    if not em:
        messages.append("❌ Email is missing.")
        return {"points": 0, "max": 10, "messages": messages}

    if re.fullmatch(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', em):
        # Disposable email domain check (basic list)
        disposable = {'mailinator.com', 'guerrillamail.com', 'tempmail.com',
                      'throwaway.email', 'yopmail.com', 'fakeinbox.com'}
        domain = em.split('@')[1]
        if domain in disposable:
            messages.append("⚠️ Email domain appears to be a disposable/temporary service.")
            return {"points": 5, "max": 10, "messages": messages}
        messages.append("✅ Email format is valid.")
        return {"points": 10, "max": 10, "messages": messages}
    else:
        messages.append("❌ Email format is invalid.")
        return {"points": 0, "max": 10, "messages": messages}


def _check_phone(phone: str) -> dict:
    """Indian mobile number: 10 digits, starting with 6-9."""
    ph = re.sub(r'[\s\-\+]', '', (phone or "").strip())
    messages = []

    if not ph:
        messages.append("⚠️ Phone number not provided.")
        return {"points": 3, "max": 10, "messages": messages}

    # Remove country code if present
    if ph.startswith('91') and len(ph) == 12:
        ph = ph[2:]
    if ph.startswith('+91'):
        ph = ph[3:]

    if re.fullmatch(r'[6-9][0-9]{9}', ph):
        # Repeated digits suspicion
        if len(set(ph)) <= 2:
            messages.append("⚠️ Phone number looks suspicious (too many repeated digits).")
            return {"points": 5, "max": 10, "messages": messages}
        messages.append("✅ Phone number is a valid Indian mobile number.")
        return {"points": 10, "max": 10, "messages": messages}
    else:
        messages.append("❌ Phone number is invalid (must be 10 digits, starting with 6-9).")
        return {"points": 0, "max": 10, "messages": messages}


def _check_location(village: str, state: str) -> dict:
    """Village and State should be non-empty."""
    messages = []
    points = 0

    if village and village.strip():
        points += 2
        messages.append("✅ Village provided.")
    else:
        messages.append("⚠️ Village name not provided.")

    if state and state.strip():
        points += 3
        messages.append("✅ State provided.")
    else:
        messages.append("⚠️ State not provided.")

    return {"points": points, "max": 5, "messages": messages}


# ──────────────────────────────────────────────────────────────────────────────
# Main scoring function
# ──────────────────────────────────────────────────────────────────────────────

def compute_genuineness_score(
    voter_id: str,
    aadhaar_last4: str,
    full_name: str,
    date_of_birth: str,
    email: str,
    phone: str,
    village: str,
    state: str,
) -> dict:
    """
    Compute a 0-100 AI genuineness score for a registration request.

    Returns:
        {
            "score": int,          # 0-100
            "label": str,          # "Genuine" / "Uncertain" / "Suspicious"
            "color": str,          # "green" / "yellow" / "red"
            "checks": {
                "voter_id": {...},
                "aadhaar":  {...},
                "age":      {...},
                "name":     {...},
                "email":    {...},
                "phone":    {...},
                "location": {...},
            },
            "summary": str,
        }
    """
    checks = {
        "voter_id": _check_voter_id(voter_id),
        "aadhaar":  _check_aadhaar(aadhaar_last4),
        "age":      _check_age(date_of_birth),
        "name":     _check_name(full_name),
        "email":    _check_email(email),
        "phone":    _check_phone(phone),
        "location": _check_location(village, state),
    }

    total_points = sum(c["points"] for c in checks.values())
    max_points   = sum(c["max"]    for c in checks.values())   # Should be 100
    score = round((total_points / max_points) * 100) if max_points else 0

    if score >= 80:
        label, color = "Genuine", "green"
    elif score >= 50:
        label, color = "Uncertain", "yellow"
    else:
        label, color = "Suspicious", "red"

    # Collect warning count for summary
    all_msgs = [m for c in checks.values() for m in c["messages"]]
    warnings = sum(1 for m in all_msgs if m.startswith("⚠️"))
    errors   = sum(1 for m in all_msgs if m.startswith("❌"))

    summary = (
        f"AI analysis complete. Score: {score}/100 ({label}). "
        f"{errors} critical issue(s), {warnings} warning(s) detected."
    )

    return {
        "score":   score,
        "label":   label,
        "color":   color,
        "checks":  checks,
        "summary": summary,
    }
