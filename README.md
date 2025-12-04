# myiq - IQ Option Trading API

[![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

An unofficial Python library for interacting with the IQ Option trading platform. This library provides a high-level API for connecting to IQ Option's WebSocket service, retrieving market data, managing accounts, and executing trades.

## ⚠️ Disclaimer

This is an **unofficial** library and is not affiliated with IQ Option. Use at your own risk. Trading involves substantial risk of loss and is not suitable for every investor.

## Features

- 🔧 Asynchronous WebSocket connection to IQ Option
- 🔐 Authentication handling
- 📈 Real-time candle streaming
- 📊 Historical candle data retrieval
- 💰 Account balance management
- 🎯 Trading execution (specifically for Blitz options)
- ⚡ Event-driven architecture with futures and callbacks

## Installation

### From PyPI (recommended)

```bash
pip install myiq
```

### From Source

```bash
pip install git+https://github.com/yourusername/myiq.git
```

Or clone the repository and install locally:

```bash
git clone https://github.com/yourusername/myiq.git
cd myiq
pip install .
```

For examples and advanced usage, you may also need the extra dependencies:

```bash
pip install myiq[examples]
```

## Quick Start

```python
import asyncio
from myiq import IQOption

async def main():
    # Initialize client
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

# Run the async function
asyncio.run(main())
```

## Usage Examples

### Retrieving Historical Candle Data

```python
import asyncio
from myiq import IQOption

async def get_candles_example():
    iq = IQOption(email="your_email@example.com", password="your_password")
    
    try:
        await iq.start()
        
        # Get EUR/USD candles (active_id=76)
        # Parameters: active_id, timeframe (seconds), count
        candles = await iq.get_candles(active_id=76, duration=60, count=100)
        
        for candle in candles:
            print(f"Time: {candle.from_time}, Open: {candle.open}, Close: {candle.close}")
            
    finally:
        await iq.close()

asyncio.run(get_candles_example())
```

### Streaming Real-Time Candle Data

```python
import asyncio
from myiq import IQOption

async def stream_candles_example():
    iq = IQOption(email="your_email@example.com", password="your_password")
    
    def on_candle(data):
        print(f"New candle: {data}")
    
    try:
        await iq.start()
        
        # Start streaming candles for EUR/USD (active_id=76)
        await iq.start_candles_stream(active_id=76, duration=60, callback=on_candle)
        
        # Keep the connection alive
        await asyncio.sleep(60)  # Stream for 60 seconds
        
    finally:
        await iq.close()

asyncio.run(stream_candles_example())
```

### Executing a Trade

```python
import asyncio
from myiq import IQOption

async def trade_example():
    iq = IQOption(email="your_email@example.com", password="your_password")
    
    try:
        await iq.start()
        
        # Get balances and select real account
        balances = await iq.get_balances()
        real_balance = next((b for b in balances if b.type == 4), None)
        if real_balance:
            await iq.change_balance(real_balance.id)
        
        # Execute a "call" option on EUR/USD
        result = await iq.buy_blitz(
            active_id=76,      # EUR/USD
            direction="call",  # "call" or "put"
            amount=1.0,        # Amount to invest
            duration=30        # Duration in seconds
        )
        
        print(f"Trade result: {result}")
        
    finally:
        await iq.close()

asyncio.run(trade_example())
```

## API Reference

### Main Classes

#### `IQOption(email: str, password: str)`

Main client for interacting with IQ Option.

##### Methods

- `async start()` - Connects to the WebSocket and authenticates the user
- `async close()` - Closes the WebSocket connection
- `get_server_timestamp() -> int` - Returns the current server timestamp in seconds
- `async get_balances() -> List[Balance]` - Retrieves account balances
- `async change_balance(balance_id: int)` - Changes the active trading balance
- `async start_candles_stream(active_id: int, duration: int, callback: Callable[[dict], None])` - Starts streaming real-time candle data
- `async get_candles(active_id: int, duration: int, count: int, to_time: Optional[int] = None) -> List[Candle]` - Retrieves historical candle data
- `async buy_blitz(active_id: int, direction: str, amount: float, duration: int = 30) -> dict` - Places a Blitz option trade

### Data Models

#### `Balance`

Represents an account balance:

```python
class Balance(BaseModel):
    id: int
    type: int
    amount: float
    currency: str
    is_fiat: bool = False
    is_marginal: bool = False
```

#### `Candle`

Represents a price candle:

```python
class Candle(BaseModel):
    id: int
    from_time: int = Field(alias="from")
    to_time: int = Field(alias="to")
    open: float
    close: float
    min: float
    max: float
    volume: float
```

## Project Structure

```
myiq/
├── core/
│   ├── client.py       # Main IQOption client
│   ├── connection.py   # WebSocket connection management
│   ├── constants.py    # API constants
│   ├── dispatcher.py   # Message routing
│   └── utils.py        # Utility functions
├── http/
│   └── auth.py         # Authentication handling
└── models/
    └── base.py         # Data models
```

## Limitations

1. **Blitz Options Only**: Currently, the library only supports trading Blitz options
2. **Limited Asset Support**: The library has been tested primarily with EUR/USD (active_id=76)
3. **No Order Management**: Advanced order management features are not implemented
4. **European Broker**: Designed for IQ Option's European broker

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- This is an unofficial library and is not affiliated with IQ Option
- Inspired by other trading API libraries
