import ast
import asyncio
import curses
import logging
import pathlib
import yaml
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
    keep_open = True

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
        while self.keep_open:
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
        if self.is_connected():
            self.writer.close()
            await self.writer.wait_closed()
            logging.info('Server connection closed')
        else: self.keep_open = False

class cursed_display:
    """
    curses display object
    """
    colors = {
        'background': -1,
        'std_text': -1,
        'menu_header': -1,
        'action_key': -1,
        'error': -1,
        'success': -1,
        'warning': -1
    }
    theme_name = ''
    stdscr = None
    serv = None

    def __init__(self, stdscr: curses.window, mdir: pathlib.Path,
                 serv: PTZ_Server, theme_name: str='default') -> None:
        self.serv = serv
        self.stdscr = stdscr
        self.theme_name = theme_name
        self.load_theme(mdir)

    def draw_menu_main(self) -> None:
        self.stdscr.clear()
        self.stdscr.addstr(
            0,0,
            '## Pautzke Bait Co., Inc. - Client',
            curses.color_pair(1)
        )
        self.stdscr.addstr(
            1,0,
            f'# Connected: {self.serv.is_connected()}',
            curses.color_pair(2)
        )
        self.stdscr.refresh()
    
    async def get_ch(self) -> int:
        self.stdscr.nodelay(True)
        while True:
            char = self.stdscr.getch()
            if char == curses.ERR: await asyncio.sleep(0)
            else: return char

    def load_theme(self, mdir: pathlib.Path) -> None:
        curses.use_default_colors()
        try:
            with open(mdir / 'themes') as file:
                themes = yaml.safe_load(file)
            for key in self.colors.keys():
                self.colors[key] = themes[self.theme_name][key]
        except FileNotFoundError as exc:
            logging.warning('Themes file not found')
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark') and exc.__context__ != None:
                logging.warning(
                    f'Failed to parse themes file:\n{str(exc.problem_mark)}\n'
                    f'{exc.problem} {exc.__context__}'
                )
            else: logging.warning('Failed to parse themes file')
        except IndexError as exc: logging.warning("Themes file invalid")
        i = 0
        for key in self.colors:
            if key == 'background': pass
            else:
                logging.info(f'val: {i}, {self.colors[key]}, {self.colors["background"]}')
                curses.init_pair(i, self.colors[key], self.colors['background'])
            i += 1

async def close_client(serv: PTZ_Server, tg:asyncio.TaskGroup) -> None:
    logging.info('Client shutdown command received')
    await serv.close()

async def console(tg: asyncio.TaskGroup, 
                  serv: PTZ_Server, display: cursed_display) -> None:
    display.draw_menu_main()
    char = await display.get_ch()
    await close_client(serv, tg)

def init_logger(mdir):
    fname = datetime.now().strftime('%Y-%m-%d') + '.log'
    logging.basicConfig(
        filename = pathlib.Path(mdir/'logs'/fname),
        level = logging.INFO,
        format = '%(levelname)s %(asctime)s %(message)s',
        datefmt = '%H:%M:%S'
    )

async def async_main(stdscr: curses.window, mdir: pathlib.Path) -> None:
    serv = PTZ_Server()
    display = cursed_display(stdscr, mdir, serv)
    async with asyncio.TaskGroup() as tg:
        serv_con = tg.create_task(serv.connect())
        con = tg.create_task(console(tg, serv, display))

def main(stdscr: curses.window) -> None:
    mdir = pathlib.Path(__file__).parent.resolve()
    init_logger(mdir)
    asyncio.run(async_main(stdscr, mdir))

if __name__ == '__main__':
    curses.wrapper(main)