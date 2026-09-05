"""화면 캡처를 해도 되는 상황인지 판단하는 정책.

화면 전체를 텍스트로 남기는 기능은 잘못 다루면 비밀번호·금융정보까지
검색 가능한 형태로 쌓이게 된다(Windows Recall이 반복해서 보안 문제를 겪은 지점).
여기서는 캡처 자체를 안 하는 것을 1차 방어선으로 삼는다.
"""

BLOCKED_BUNDLE_IDS = {
    "com.apple.keychainaccess",
    "com.1password.1password",
    "com.agilebits.onepassword7",
    "com.bitwarden.desktop",
    "com.lastpass.LastPass",
    "com.dashlane.Dashlane",
    "com.apple.systempreferences",
    "com.apple.Passwords",
}

BLOCKED_APP_KEYWORDS = (
    "1password", "bitwarden", "lastpass", "dashlane", "keychain",
    "비밀번호", "password", "은행", "bank", "toss", "뱅크",
)

SENSITIVE_TITLE_KEYWORDS = (
    "비밀번호", "password", "passwd", "secret", "credential",
    "카드번호", "계좌", "주민등록", "otp", "인증번호",
    "api key", "api_key", "token", "private key",
)


def is_app_blocked(app_name: str, bundle_id: str = "") -> bool:
    if bundle_id and bundle_id.lower() in BLOCKED_BUNDLE_IDS:
        return True
    lowered = (app_name or "").lower()
    return any(keyword in lowered for keyword in BLOCKED_APP_KEYWORDS)


def contains_sensitive_text(text: str) -> bool:
    """OCR 결과에 민감어가 섞이면 그 캡처분은 통째로 버린다."""
    lowered = text.lower()
    return any(keyword in lowered for keyword in SENSITIVE_TITLE_KEYWORDS)
