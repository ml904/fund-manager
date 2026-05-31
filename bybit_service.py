import os
from pybit.unified_trading import HTTP


def get_session():
    return HTTP(
        testnet=False,
        api_key=os.environ.get("BYBIT_API_KEY", ""),
        api_secret=os.environ.get("BYBIT_API_SECRET", ""),
    )


def get_solde_usdt():
    """Return total USDT equity from Unified Trading Account."""
    try:
        session = get_session()
        resp = session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        accounts = resp.get("result", {}).get("list", [])
        if accounts:
            for coin_info in accounts[0].get("coin", []):
                if coin_info.get("coin") == "USDT":
                    return float(coin_info.get("equity", 0))
        return 0.0
    except Exception as e:
        print(f"[Bybit] Erreur lecture solde: {e}")
        return None
