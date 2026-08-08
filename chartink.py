import re
from typing import Any, Dict, List, Optional

import requests

BASE_URL = "https://chartink.com"
SCREENER_URL = f"{BASE_URL}/screener/india"
PROCESS_URL = f"{BASE_URL}/screener/process"


class ChartinkClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
        )
        self._csrf_token: Optional[str] = None

    def _refresh_csrf_token(self) -> str:
        response = self.session.get(SCREENER_URL, timeout=30)
        response.raise_for_status()
        match = re.search(r'<meta[^>]+name="csrf-token"[^>]+content="([^\"]+)"', response.text)
        if not match:
            raise RuntimeError("Unable to extract Chartink CSRF token.")
        self._csrf_token = match.group(1)
        return self._csrf_token

    def _csrf(self) -> str:
        if not self._csrf_token:
            return self._refresh_csrf_token()
        return self._csrf_token

    def run_scan(
        self,
        scan_clause: str,
        column_clause: str,
        debug_clause: str = "",
        timeout: int = 30,
    ) -> Dict[str, Any]:
        token = self._csrf()
        payload = {
            "scan_clause": scan_clause,
            "debug_clause": debug_clause,
            "column_clause": column_clause,
        }
        headers = {
            "Referer": SCREENER_URL,
            "X-CSRF-Token": token,
            "X-Requested-With": "XMLHttpRequest",
        }
        response = self.session.post(PROCESS_URL, data=payload, headers=headers, timeout=timeout)
        response.raise_for_status()

        try:
            result = response.json()
        except ValueError as exc:
            raise RuntimeError("Chartink returned invalid JSON") from exc

        if isinstance(result, dict) and result.get("scan_error"):
            raise RuntimeError(f"Chartink scan failed: {result['scan_error']}")

        if isinstance(result, dict) and not result.get("data") and result.get("link"):
            raise RuntimeError(
                "Chartink returned scan link instead of direct results. "
                "Try narrowing the scan or use a smaller column set."
            )

        return result

    def scan_candidates(
        self,
        scan_clause: str,
        column_clause: str,
        max_candidates: int = 300,
    ) -> List[Dict[str, Any]]:
        result = self.run_scan(scan_clause=scan_clause, column_clause=column_clause)
        rows = result.get("data") or []
        return rows[:max_candidates]
