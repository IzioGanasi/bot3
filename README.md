---

# 📚 Documentação Oficial: myiq

A `myiq` é uma biblioteca **assíncrona** baseada em `asyncio` para interação com a IQ Option. Diferente de bibliotecas síncronas antigas, ela utiliza um sistema de **Dispatcher** e **Futures** para gerenciar eventos do WebSocket.

Esta documentação cobre **todos** os métodos disponíveis na classe principal `IQOption`, explicando parâmetros, retornos e exemplos de uso.

---

## Instalação

```python
pip install git+https://github.com/IzioGanasi/bot3.git
```

## 🚀 Índice

1. [Inicialização e Conexão](#1-inicialização-e-conexão)
   - `__init__`
   - `start()`
   - `close()`
2. [Sincronização de Tempo](#2-sincronização-de-tempo)
   - `get_server_timestamp()`
3. [Gestão de Saldo](#3-gestão-de-saldo)
   - `get_balances()`
   - `change_balance()`
4. [Dados de Mercado (Candles)](#4-dados-de-mercado-candles)
   - `get_candles()` (Histórico Simples)
   - **[Técnica Avançada]** Coletando +1000 Candles
   - `start_candles_stream()` (Tempo Real)
5. [Trading (Blitz)](#5-trading-blitz)
   - `buy_blitz()`
6. [Arquitetura de Reconexão](#6-arquitetura-de-reconexão-automática)

---

## 1. Inicialização e Conexão

### `__init__(email: str, password: str)`
Instancia o cliente. Não conecta imediatamente.
- **Parâmetros:** Credenciais da IQ Option.

### `start()`
**Método Assíncrono.** Realiza a sequência completa de login:
1. Obtém o SSID via HTTP.
2. Abre a conexão WebSocket.
3. Envia mensagem de autenticação.
4. Inscreve-se nos canais de portfólio (necessário para receber resultados de trade).

### `close()`
**Método Assíncrono.** Fecha a conexão WebSocket de forma limpa e define `self.connected = False`.

#### Exemplo de Ciclo de Vida:
```python
import asyncio
from myiq import IQOption

async def lifecycle_example():
    # 1. Instanciação
    iq = IQOption("seu_email@teste.com", "sua_senha")
    
    # 2. Conexão
    print("Iniciando conexão...")
    await iq.start()
    
    if iq.connected:
        print(f"Conectado! SSID: {iq.ssid}")
    
    # ... faz operações ...

    # 3. Fechamento
    await iq.close()
    print("Conexão encerrada.")

if __name__ == "__main__":
    asyncio.run(lifecycle_example())
```

---

## 2. Sincronização de Tempo

### `get_server_timestamp() -> int`
Retorna o timestamp atual do servidor da IQ Option (em segundos). A biblioteca calcula automaticamente o *offset* (atraso) entre sua máquina e o servidor para garantir precisão na abertura de ordens e fechamento de velas.

- **Retorno:** Inteiro (Epoch timestamp).

#### Exemplo:
```python
ts = iq.get_server_timestamp()
print(f"Hora do servidor: {ts}")
# Útil para calcular o parâmetro 'to_time' ao pedir candles
```

---

## 3. Gestão de Saldo

### `get_balances() -> List[Balance]`
**Método Assíncrono.** Solicita ao servidor todos os saldos disponíveis para o perfil.
- **Retorno:** Uma lista de objetos `Balance` (Pydantic models).
- **Atributos do objeto Balance:** `id`, `amount`, `currency`, `type` (1=Real, 4=Treinamento).

#### Exemplo:
```python
balances = await iq.get_balances()
for b in balances:
    tipo = "Real" if b.type == 1 else "Treinamento" if b.type == 4 else "Outro"
    print(f"[{tipo}] ID: {b.id} | Saldo: {b.amount} {b.currency}")
```

### `change_balance(balance_id: int)`
**Método Assíncrono.** Define qual carteira será utilizada para as operações de trading. **Obrigatório chamar antes de operar.**

#### Exemplo:
```python
# Supondo que você já pegou a lista com get_balances()
id_treinamento = 12345678  # ID obtido do passo anterior
await iq.change_balance(id_treinamento)
print(f"Saldo {id_treinamento} ativado para operações.")
```

---

## 4. Dados de Mercado (Candles)

### `get_candles(active_id, duration, count, to_time=None) -> List[Candle]`
**Método Assíncrono.** Busca histórico de velas.
- `active_id` (int): ID do ativo (Ex: 76 para EURUSD, 1 para EURGBP).
- `duration` (int): Tempo em segundos (60, 300, 900, etc).
- `count` (int): Quantidade de velas (Máx: 1000).
- `to_time` (int, opcional): Timestamp do final da busca. Se `None`, usa o tempo atual.

#### Exemplo Simples:
```python
# Pega as últimas 10 velas de 1 minuto do EURUSD (76)
candles = await iq.get_candles(76, 60, 10)
for c in candles:
    print(f"Abertura: {c.open} | Fechamento: {c.close}")
```

### 🌟 Técnica Avançada: Coletando +1000 Candles
Como a API limita a 1000 velas por pedido, devemos criar uma função que faz "paginação" baseada no tempo, recuando no histórico.

```python
async def get_thousands_candles(iq_instance, active_id, duration, total_required):
    """
    Coleta mais de 1000 candles fazendo requisições em loop.
    """
    all_candles = []
    # Começa pedindo a partir do momento atual do servidor
    current_to_time = iq_instance.get_server_timestamp()
    
    while len(all_candles) < total_required:
        # Calcula quantos faltam, limitado a 1000 por lote
        remaining = total_required - len(all_candles)
        batch_size = min(1000, remaining)
        
        print(f"Baixando lote de {batch_size} velas...")
        
        # Faz a requisição
        batch = await iq_instance.get_candles(active_id, duration, batch_size, to_time=current_to_time)
        
        if not batch:
            break  # Sem mais dados
            
        # Organiza: a API retorna do antigo -> novo.
        # Nós queremos acumular tudo numa lista histórica.
        # Adicionamos o lote novo ANTES do que já temos
        all_candles = batch + all_candles
        
        # O próximo 'to_time' deve ser o 'from_time' da vela mais antiga recebida
        # menos 1 segundo para evitar duplicação exata
        oldest_candle_in_batch = batch[0]
        current_to_time = oldest_candle_in_batch.from_time - 1
        
        # Pequeno delay para evitar flood
        await asyncio.sleep(0.2)
        
    return all_candles

# Uso:
# historico = await get_thousands_candles(iq, 76, 60, 5000)
# print(f"Total coletado: {len(historico)}")
```

### `start_candles_stream(active_id, duration, callback)`
**Método Assíncrono.** Inscreve-se para receber velas em tempo real via WebSocket.
- `callback`: Uma função (pode ser async ou sync) que será chamada a cada atualização de vela.

#### Exemplo:
```python
def processar_vela(data: dict):
    # 'data' é um dicionário cru enviado pelo WebSocket
    id_ativo = data.get('active_id')
    preco_atual = data.get('close')
    print(f"Stream Ativo {id_ativo}: $ {preco_atual}")

# Inicia o stream
await iq.start_candles_stream(76, 60, processar_vela)

# Nota: Você precisa manter o event loop rodando (asyncio.sleep) para continuar recebendo
```

---

## 5. Trading (Blitz)

### `buy_blitz(active_id, direction, amount, duration) -> dict`
**Método Assíncrono.** Executa uma ordem de opções Blitz. Este método é complexo: ele envia a ordem, espera o ID ser gerado, subscreve para monitorar esse ID e espera o resultado final (win/loss).

- `active_id` (int): ID do ativo (Ex: 76).
- `direction` (str): "call" (compra) ou "put" (venda).
- `amount` (float): Valor da entrada.
- `duration` (int): Expiração em segundos (Ex: 30, 60).

- **Retorno (dict):**
  - `status`: "completed" ou "error".
  - `result`: "win", "loose", "equal".
  - `profit`: Valor numérico do lucro ou prejuízo.

#### Exemplo:
```python
try:
    print("Enviando ordem de compra no EURUSD...")
    resultado = await iq.buy_blitz(
        active_id=76, 
        direction="call", 
        amount=2.0, 
        duration=30
    )
    
    if resultado['status'] == 'completed':
        lucro = resultado['profit']
        print(f"Ordem finalizada! Resultado: {resultado['result']} | Lucro: {lucro}")
    else:
        print("Erro: Timeout ou falha na execução.")
        
except ValueError as e:
    print(f"Erro de validação (provavelmente sem saldo selecionado): {e}")
```

---

## 6. Arquitetura de Reconexão Automática

A biblioteca `myiq` foca em transparência e não esconde a desconexão de você. Se a conexão cair, o `iq.connected` eventualmente se tornará falso ou métodos lançarão erro.

O padrão correto para criar um bot resiliente (24/7) é encapsular a lógica do bot em uma função e rodá-la dentro de um loop infinito externo.

```python
import asyncio
import structlog
from myiq import IQOption

logger = structlog.get_logger()

# 1. Sua estratégia isolada
async def trader_strategy(iq):
    """
    Aqui vai a lógica que roda ENQUANTO estiver conectado.
    """
    # Configurações iniciais
    balances = await iq.get_balances()
    # Exemplo: pega o primeiro saldo tipo 4 (treino)
    demo_balance = next((b for b in balances if b.type == 4), None)
    if demo_balance:
        await iq.change_balance(demo_balance.id)
    
    # Loop da estratégia
    while iq.connected:
        # Exemplo simples: a cada 5 segundos imprime o timestamp
        ts = iq.get_server_timestamp()
        logger.info("Bot rodando", time=ts)
        
        # Aqui você colocaria:
        # - Análise de indicadores
        # - Verificação de sinais
        # - buy_blitz()
        
        await asyncio.sleep(5)

# 2. O Loop de Reconexão (Main Loop)
async def main_reconnect_loop():
    email = "email@exemplo.com"
    password = "senha"
    
    while True:
        # Cria nova instância a cada tentativa para limpar estados antigos
        iq = IQOption(email, password)
        try:
            logger.info("Tentando conectar...")
            await iq.start()
            
            if iq.connected:
                logger.info("Conectado com sucesso. Iniciando estratégia.")
                # Passa o controle para a estratégia
                # Se cair lá dentro, essa função retorna e o loop reinicia
                await trader_strategy(iq)
            else:
                logger.error("Falha ao iniciar conexão (iq.connected False).")

        except Exception as e:
            logger.error("Erro crítico na conexão ou estratégia", error=str(e))
        
        finally:
            # Limpeza
            try:
                if iq.connected: # Se ainda acha que está conectado, fecha
                    await iq.close()
            except:
                pass
            
            logger.info("Aguardando 10 segundos para reconectar...")
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main_reconnect_loop())
    except KeyboardInterrupt:
        print("Bot parado pelo usuário.")
```
