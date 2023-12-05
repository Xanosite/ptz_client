import ast
import asyncio
import curses
import logging
import pathlib
from datetime import datetime

MAGIC = 'pr7d68j1'
M_PORT = int(50201)
VERSION = 0.3

class PTZ_Server:
    """
    Server object
    """
    c_addr = None
    connected = False
    port = None
    reader = None
    retry_timer = 5
    s_addr = None
    writer = None

    def __init__(self, s_addr: str='fc0', port: int=M_PORT) -> None:
        self.s_addr = s_addr
        self.port = port
    
    def get_c_addr(self) -> str: return self.c_addr
    def get_port(self) -> int: return self.port
    def get_reader(self)  -> asyncio.StreamReader: return self.reader
    def get_s_addr(self) -> str: return self.s_addr
    def get_writer(self) -> asyncio.StreamWriter: return self.writer

    def is_connected(self) -> bool: return self.connected

    def set_c_addr(self, addr: str) -> None: self.c_addr = addr
    def set_connected(self, status: bool) -> None: self.connected = status
    def set_port(self, port: int) -> None: self.port = port
    def set_reader(self, reader) -> None: self.reader = reader
    def set_s_addr(self, s_addr) -> None: self.s_addr = s_addr
    def set_writer(self, writer) -> None: self.writer = writer

    async def connect(self):
        """
        Connect to the ptz_server
        """
        while True:
            logging.info(
                f'Attempting to connect to server at {self.s_addr}:{self.port}'
            )
            try:
                reader, writer = await asyncio.open_connection(
                    self.s_addr, self.port
                )
            except OSError as err:
                logging.info(
                    f'Connection to server at {self.s_addr}:{self.port} failed,'
                    f' retry in {self.retry_timer}s: {err}'
                )
                await asyncio.sleep(self.retry_timer)
            else:
                self.reader = reader
                self.writer = writer
                if self.handshake():
                    logging.info(
                        f'Connected to server at {self.s_addr}:{self.port}'
                    )
                    self.connected = True
                    break
                else: 
                    logging.waring(
                        f'Bad handshake with server at {self.s_sddr}:'
                        f'{self.port}'
                    )
                    await asyncio.sleep(self.retry_timer)

    async def handshake(self) -> bool:
        data = await self.receive()
        if 'version' in data.keys(): status = data['version'] == VERSION 
        data = {'version':VERSION, 'magic':MAGIC}
        await self.send(data)
        return status

    async def receive(self) -> dict:
        b_data = b''
        while True:
            chunk = await self.reader.read(1024)
            if chunk == b'': break
            else: b_data += chunk
        data = ast.literal_eval(b_data.decode('utf-8'))
        if self.writer == None: logging.debug(f'Received data: {data}')
        else: logging.debug(
            f'Client {self.paddr} received data from {self.addr}: {data}'
        )
        return data

    async def send(self, data: dict) -> None:
        logging.debug(f'Client {self.addr} sending data to {self.paddr}: {data}')
        b_data = bytes(str(data), 'utf-8')
        self.writer.write(b_data)
        await self.writer.drain()
        self.writer.write_eof()    

    async def close(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()
        logging.info('Server connection closed')

def main(stdscr: curses.window) -> None:
    mdir = pathlib.Path(__file__).parent.resolve()
    init_logger(mdir)
    asyncio.run(async_main(stdscr))

async def async_main(stdscr: curses.window) -> None:
    serv = PTZ_Server()
    async with asyncio.TaskGroup() as tg:
        serv_con = tg.create_task(serv.connect())
        con = tg.create_task(console(stdscr, tg, serv))
    serv.close()

async def console(stdscr: curses.window, tg: asyncio.TaskGroup, 
                  serv: PTZ_Server) -> None:
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    async def display_menu_main() -> None:
        stdscr.clear()
        stdscr.addstr(
            0,0,
            '## Pautzke Bait Co., Inc. - Client',
            curses.color_pair(1)
        )
        stdscr.addstr(
            1,0,
            f'# Connected: {serv.is_connected()}',
            curses.color_pair(2)
        )
        stdscr.refresh()
# TODO: add main menu, especially updating of server status and shutting down of said server

    await display_menu_main()
def init_logger(mdir):
    fname = datetime.now().strftime('%Y-%m-%d') + '.log'
    logging.basicConfig(
        filename = pathlib.Path(mdir/'logs'/fname),
        level = logging.INFO,
        format = '%(levelname)s %(asctime)s %(message)s',
        datefmt = '%H:%M:%S'
    )

if __name__ == '__main__':
    curses.wrapper(main)