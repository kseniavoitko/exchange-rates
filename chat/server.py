import asyncio
import logging

import aiohttp
from datetime import datetime, date, timedelta
import websockets
import names
from websockets import WebSocketServerProtocol, WebSocketProtocolError
from websockets.exceptions import ConnectionClosedOK


logging.basicConfig(level=logging.INFO)


async def request(url):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    r = await response.json()
                    return r
                logging.error(f"Error status {response.status} for {url}")
        except aiohttp.ClientConnectorError as e:
            logging.error(f"Connection error {url}: {e}")
        return None


async def get_exchange(args):
    result = ""
    current_date = date.today()
    try:
        days = int(args[0]) if len(args) > 0 else 1
    except ValueError:
        return "First parameter must be a numder"
    if days > 10:
        return "Days of exchange rates must be less than 11"
    rates = ["USD", "EUR"]
    if len(args) > 1:
        rates.extend(args[1].split(','))  
    for day in range(days):
        days_interval = timedelta(days=day)
        day_of_exchange = (current_date - days_interval).strftime('%d.%m.%Y')
        res = await request("https://api.privatbank.ua/p24api/exchange_rates?json&date=" + day_of_exchange)
        exchange = list(filter(lambda el: el["currency"] in rates, res['exchangeRate']))
        result += f"date {day_of_exchange} |"
        for rate in exchange:
            result += f"{rate['currency']}: purchase: {rate['purchaseRateNB']}, sale: {rate['saleRateNB']} |"
    return result


class Server:
    clients = set()

    async def register(self, ws: WebSocketServerProtocol):
        ws.name = names.get_full_name()
        self.clients.add(ws)
        logging.info(f"{ws.remote_address} connects")

    async def unregister(self, ws: WebSocketServerProtocol):
        self.clients.remove(ws)
        logging.info(f"{ws.remote_address} disconnects")

    async def send_to_clients(self, message: str):
        if self.clients:
            [await client.send(message) for client in self.clients]

    async def send_to_client(self, message: str, ws: WebSocketServerProtocol):
        await ws.send(message)

    async def ws_handler(self, ws: WebSocketServerProtocol):
        await self.register(ws)
        try:
            await self.distrubute(ws)
        except ConnectionClosedOK:
            pass
        finally:
            await self.unregister(ws)

    async def distrubute(self, ws: WebSocketServerProtocol):
        async for message in ws:
            command, *args = message.split(" ")
            if command == "exchange":
                r = await get_exchange(args)
                await self.send_to_client(r, ws)
            else:
                await self.send_to_clients(f"{ws.name}: {message}")


async def main():
    server = Server()
    async with websockets.serve(server.ws_handler, "localhost", 8080):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
