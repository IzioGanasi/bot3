"""
Example usage of the myiq library.
"""

import asyncio
from myiq import IQOption

async def main():
    # Initialize client (replace with your credentials)
    iq = IQOption(email="your_email@example.com", password="your_password")
    
    try:
        # Connect and authenticate
        await iq.start()
        print("Connected successfully!")
        
        # Get account balances
        balances = await iq.get_balances()
        for balance in balances:
            print(f"{balance.type_name}: {balance.amount} {balance.currency}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Close connection
        await iq.close()

if __name__ == "__main__":
    asyncio.run(main())