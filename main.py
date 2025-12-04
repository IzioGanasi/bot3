import asyncio
from getpass import getpass
import logging
from datetime import datetime

from bot_pro import MomentumProBot  # ou bot_ml.MomentumMLBot conforme você tenha
from myiq import IQOption

# logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)

ACTIVE_ID = 76   # EUR/USD
TIMEFRAME = 60   # 1 minuto

async def main():
    print("\n=== IQ OPTION LOGIN ===")
    email = input("Email: ")
    password = getpass("Senha: ")

    iq = IQOption(email, password)

    print("\n🔌 Conectando...")
    await iq.start()
    print("✅ Cliente iniciado (start executado).")

    # obter saldos
    print("\n💰 Obtendo saldos...")
    balances = await iq.get_balances()
    if not balances:
        print("❌ Nenhum saldo encontrado.")
        await iq.close()
        return

    # preferir real (type=4) com saldo
    balance = next((b for b in balances if b.type == 4 and b.amount > 0), None)
    if not balance:
        balance = balances[0]

    await iq.change_balance(balance.id)
    # usar type_name seguro (agora disponível no modelo)
    print(f"➡ Usando saldo: {balance.type_name} | {balance.currency} {balance.amount}")

    # instanciar bot (use bot_pro.py criado antes)
    bot = MomentumProBot(iq, ACTIVE_ID, TIMEFRAME, min_confidence=0.72, vol_threshold=0.0001, use_mlp=False)
    await bot.start(initial_history=200)

    print("\n🚀 BOT ATIVO! Aguardando candles...\n")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 BOT finalizado manualmente.")
    finally:
        # encerra conexões
        await iq.close()
        print("🔌 Conexão encerrada.")

if __name__ == "__main__":
    asyncio.run(main())
