import httpx
from typing import Optional

class IQAuth:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def get_ssid(self) -> str:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {"identifier": self.email, "password": self.password}
            try:
                resp = await client.post("https://auth.iqoption.com/api/v2/login", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    # Forma esperada pode variar; ajuste conforme resposta real
                    if data.get("code") == "success":
                        return data.get("ssid", "")
                    # fallback: procurar chave ssid
                    return data.get("ssid", "") or ""
            except Exception:
                return ""
        return ""
