import functools
import json
import re
import threading
from sys import stdout

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init
from fake_useragent import UserAgent

MAX_THREADS = 500
PROXY_TIMEOUT = 5
RE_PROXY = re.compile(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,4}[0-5]?")
RE_URL = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
PROXY_TYPES = [
    ('https', '', 'HTTPS'),
    ('http', 'http://', 'HTTP'),
    ('http', 'socks5h://', 'SOCKS5'),
    ('http', 'socks4://', 'SOCKS4')
]
TEST_DOMAIN = 'google.com'
OUTPUT_JSON = 'proxies.json'
OUTPUT_TXT_SUFFIX = 'PROXIES'
BANNER = """
________                                   ______________       _________            
___  __ \________________  ______  __      ___  ____/__(_)____________  /____________
__  /_/ /_  ___/  __ \_  |/_/_  / / /________  /_   __  /__  __ \  __  /_  _ \_  ___/
_  ____/_  /   / /_/ /_>  < _  /_/ /_/_____/  __/   _  / _  / / / /_/ / /  __/  /    
/_/     /_/    \____//_/|_| _\__, /        /_/      /_/  /_/ /_/\__,_/  \___//_/     
                            /____/                              Coded By Kacperek1337
"""
THREADS = []
PROXIES = []
WORKING_PROXIES = []

def status(info, level=1):
    levels = {
        0: Fore.GREEN + "[+]",
        1: Fore.BLUE + "[*]",
        2: Fore.YELLOW + "[-]",
        3: Fore.RED + "[!]"
    }
    stdout.write(Style.BRIGHT + levels.get(level) + Style.RESET_ALL + ' ' + info + '\n')

def catch_exception(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            val = func(*args, **kwargs)
            return val
        except Exception as e:
            status("An exception occurred: %s"%e, 3)
    return wrapper

class DuckDuckGo:

    @catch_exception
    def search(self, query):
        headers = {
            'User-Agent': UserAgent().random
        }
        data = {
            'q': query
        }
        if len(query) > 40:
            raise ValueError("Query too long")
        while True:
            response = requests.post('https://lite.duckduckgo.com/lite/', data=data, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in [a['href'] for a in soup.find_all('a', href=True)]:
                if link not in self._results and RE_URL.match(link) is not None:
                    self._results.append(link)
            next_page_form = soup.find('form', attrs={
                'class': 'next_form'
            })
            if not next_page_form:
                return
            data = {}
            for inp in next_page_form.find_all('input', attrs={
                'type': 'hidden'
            }):
                data.update({
                    inp['name']: inp['value']
                })

    def get_results(self):
        results = self._results
        self._results = []
        return results

    def __init__(self):
        self._results = []

def active_count():
    t_count = 0
    for thread in THREADS:
        if thread.is_alive():
            t_count += 1
    return t_count

def join_all():
    for thread in THREADS:
        thread.join()

class Thread(threading.Thread):

    def start(self, *args, **kwargs):
        while active_count() > MAX_THREADS:
            pass
        super().start(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        THREADS.append(self)
        super().__init__(*args, **kwargs)

    def __del__(self):
        THREADS.remove(self)

@catch_exception
def find_proxies_in_url(url):
    response = requests.get(url, headers={
        'User-Agent': UserAgent().random
    }, timeout=10)
    if response.status_code != 200:
        status('%s returned status code %d'%(url, response.status_code), 2)
        return
    for proxy in RE_PROXY.findall(response.text):
        if proxy not in PROXIES:
            PROXIES.append(proxy)
    
def check_proxy(proxy):
    for p_type in PROXY_TYPES:
        try:
            response = requests.get(p_type[0] + '://' + TEST_DOMAIN, proxies={
                p_type[0]: p_type[1] + proxy
            }, timeout=PROXY_TIMEOUT, headers={
                'User-Agent': UserAgent().random
            })
            response_time = int(response.elapsed.total_seconds() * 1000)
            status(f'Found working {p_type[2]} proxy {proxy} - Response time: {response_time}ms', 0)
            WORKING_PROXIES.append({
                'Type': p_type[2],
                'Address': proxy,
                'ResponseTime': response_time
            })
            return
        except Exception:
            pass
    else:
        status(f'{proxy} is dead', 2)

if __name__ == '__main__':
    init()
    print(Fore.CYAN + BANNER + Fore.RESET)
    try:
        ddg = DuckDuckGo()
        status('Querying DuckDuckGo')
        for keyword in map(lambda k: k.strip('\n'), open('keywords.txt', 'r').readlines()):
            status(f'Searching for "{keyword}"...')
            ddg.search(keyword)
        urls = ddg.get_results()
        status(f'Found {len(urls)} URLs', 0)
        for url in urls:
            Thread(target=find_proxies_in_url, args=[url]).start()
        join_all()
        status(f'Found {len(PROXIES)} possibly working proxies', 0)
        status('Checking proxies... It may take some time')
        for proxy in PROXIES:
            Thread(target=check_proxy, args=[proxy]).start()
        join_all()
        status('Finished checking proxies')
        status(f'Found {len(WORKING_PROXIES)} working proxies', 0)
        with open(OUTPUT_JSON, 'w') as file:
            json.dump(WORKING_PROXIES, file)
        output_filenames = [t[2] + '_' + OUTPUT_TXT_SUFFIX for t in PROXY_TYPES]
        output_files = [open(f, 'w') for f in output_filenames]
        for proxy in WORKING_PROXIES:
            [f for f in output_files if f.name.split('_')[0] == proxy['Type']][0].write(proxy['Address'] + '\n')
        output_filenames.append(OUTPUT_JSON)
        status('Proxies written to files: %s'%', '.join(output_filenames), 0)
    except (SystemExit, KeyboardInterrupt):
        status(Fore.YELLOW + 'Exiting...' + Fore.RESET, 3)
