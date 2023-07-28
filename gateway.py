import asyncio
from dataclasses import dataclass
import datetime
import time
import traceback
import zlib
import websockets
import json
import random
import requests
from asyncio import *
from websockets.exceptions import *

uptime = time.time()
USERNAME_BOT = None
USER_AGENT = 'DiscordBot (Gingantic, 0.1)'
TOKEN = "MTExMTY4MzEwNzE3MTYxNDgyMQ.GjYMTu.UmOioEHl96Me3OVP0bN3PZY0LpSzoKnaM6dchs"
GATEAWAY_URL = 'wss://gateway.discord.gg/?v=10&encoding=json&compress=zlib-stream'
API_URL = 'https://discord.com/api/v10/'
RESUME_STATUS = False
SET_INTENT = 3276799
INTERVAL_HEARTBEAT = None
CHAT_GPT_ENDPOINT = "http://vps.gins.my.id:1337/chat/completions"
CHAT_GPT_DIALOG = None
CHAT_GPT_SAVE_PATH = "historygpt.json"
CHAT_GPT_TEMPLATE_USER = None
ENABLE_CHAT_GPT = True
HEADER_API = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": USER_AGENT
}
CHANNEL_ID_CLYDE = "1128739121582575696"
# first array is channel_id, second array is message_id, third array is message
UNANSWERED_MESSAGE = []
WHITE_LIST_CHANNEL = ["1028580720655999067","477911432709799936", "521713650302713869"]
AUTHOR_USERNAME = "gingantic"

class RateLimiter:
    def __init__(self, max_calls, time_period):
        self.max_calls = max_calls
        self.time_period = time_period
        self.call_count = 0
        self.last_reset_time = time.time()

    def call(self):
        current_time = time.time()
        time_elapsed = current_time - self.last_reset_time

        if time_elapsed > self.time_period:
            self.call_count = 0
            self.last_reset_time = current_time

        if self.call_count < self.max_calls:
            self.call_count += 1
            return True
        else:
            print("Rate limit exceeded.")
            return False

    def get_remaining_calls(self):
        remaining_calls = self.max_calls - self.call_count
        return max(0, remaining_calls)

limiter = RateLimiter(max_calls=10, time_period=3600)

@dataclass
class GatewayMessage():
    op: int
    data: object
    sequence: int
    name: str

def _GateMsg(msg):
    obj = json.loads(msg) 
    op = None
    data = None
    seq = None
    name = None
    if "op" in obj:
        op = obj["op"]
    if "d" in obj:
        data = obj["d"]
    if "s" in obj:
        seq = obj["s"]
    if "t" in obj:
        name = obj["t"]
    return GatewayMessage(op, data, seq, name)

ZLIB_SUFFIX = b'\x00\x00\xff\xff'
buffer = bytearray()
inflator = zlib.decompressobj()

async def decompress_data(msg):
    global buffer
    try:
        buffer.extend(msg)
        if len(msg) < 4 or msg[-4:] != ZLIB_SUFFIX:
            return None
        msg = inflator.decompress(buffer)
        buffer = bytearray()
        return _GateMsg(msg)
    except Exception as e:
        return _GateMsg("{}")

def get_datetime():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

async def connect_to_gateway():
    async with websockets.connect(GATEAWAY_URL) as ws:
        try:
            while True:
                recv = await ws.recv()
                payload = await decompress_data(recv)
                opcode = payload.op
                seq = payload.sequence
                data = payload.data
                name = payload.name

                print(f"{get_datetime()} - {payload.op}")
                
                if opcode == 10:
                    interval = data['heartbeat_interval'] / 1000
                    asyncio.create_task(send_heartbeat(ws, interval))
                    await send_identify(ws)
                elif opcode == 11:
                    print('Heartbeat ACK received')
                elif opcode == 7:
                    print('Reconnect received')
                    print(payload)
                    await send_message("1028580720655999067", f"OP 7 Reconnect again\nUptime ke - {uptime}")
                    await ws.close()
                    await connect_to_gateway()
                elif opcode == 9:
                    print('Invalid session received')
                    await ws.close()
                    await connect_to_gateway()
                elif opcode == 0:
                    await handle_event(ws, name, data)
                elif opcode is None:
                    print('Opcode is None')
                    await ws.close()
                    await connect_to_gateway()
        except ConnectionClosedError as e:
            print(f'[{get_datetime()}] Connection error closed with code: {e.code} and reason: {e.reason}')
            traceback.print_exc()
            await connect_to_gateway()

        except ConnectionClosedOK as e:
            print(f'[{get_datetime()}] Connection closed with code: {e.code} and reason: {e.reason}')
            traceback.print_exc()
            await connect_to_gateway()

        except Exception as e:
            print(f'[{get_datetime()}] Exception: {e}')
            ws.close()
            traceback.print_exc()
            await connect_to_gateway()


async def send_identify(ws):
    #"intents": 3276799,
    identify_data = {
        "op": 2,
        "d": {
            "token": TOKEN,
            "intents": SET_INTENT,
            "properties": {
                "$os": "linux",
                "$browser": "my_library",
                "$device": "my_library"
            }
        }
    }
    await ws.send(json.dumps(identify_data))

async def custom_status(ws):
    while True:
        uptime_time = time.time() - uptime
        uptime_time_format = str(datetime.timedelta(seconds=uptime_time)).split(".")[0]
        payload = {
            "op": 3,
            "d": {
                "status": "dnd",
                "since": 0,
                "activities": [
                    {
                        "name": "Custom Status",
                        "type": 4,
                        "state": f"Uptime Test {uptime_time_format}",
                        "emoji": None
                    }
                ],
                "afk": False
            }
        }
        await ws.send(json.dumps(payload))
        await asyncio.sleep(random.randrange(15, 30))

async def send_heartbeat(ws, interval):
    while True:
        await asyncio.sleep(interval)
        heartbeat_data = {
            'op': 1,
            'd': None
        }
        await ws.send(json.dumps(heartbeat_data))

async def handle_event(ws, event_type, event_data):
    global USERNAME_BOT
    if event_type == 'READY':
        print('Ready event received')
        USERNAME_BOT = event_data['user']['username']
        print(USERNAME_BOT)
        asyncio.create_task(custom_status(ws))
        await send_message("1028580720655999067", f"Bot lauched")

    elif event_type == 'MESSAGE_CREATE':
        await handle_message(ws, event_data)

async def handle_message(ws, message_data):
    global ENABLE_CHAT_GPT
    try:
        id_message = message_data['id']
        author = message_data['author']['username']
        name = message_data['author']['global_name']
        mention_id = message_data['mentions']
        first_mention = None
        content = message_data['content']
        channel_id = message_data['channel_id']
        split_content = content.split(" ")
        for i in mention_id:
            if i['username'] == USERNAME_BOT:
                first_mention = i
                break
        if not channel_id in WHITE_LIST_CHANNEL:
            return
        if USERNAME_BOT in str(message_data['mentions']):
            await send_message(channel_id, f"Halo {name}!", reply_id=message_data['id'])
        if ">uptime" == content:
            uptime_time = time.time() - uptime
            uptime_time_format = str(datetime.timedelta(seconds=uptime_time)).split(".")[0]
            await send_message(channel_id, f"Uptime: {uptime_time_format}")
        elif ">ping" == content:
            await send_message(channel_id, "Pong")
        elif ">chat_disable" == content and author == "gingantic":
            ENABLE_CHAT_GPT = False
            await send_message(channel_id, "GPT is disabled")
        elif ">chat_enable" == content and author == "gingantic":
            ENABLE_CHAT_GPT = True
            await send_message(channel_id, "GPT is enabled")
        elif [">chat",">ask",">askchat"] in split_content[0]:
            if not limiter.call():
                await send_message(channel_id,"Rate limiter aktif, tunggu beberapa saat")
                return
            if not ENABLE_CHAT_GPT:
                await send_message(message_data['channel_id'], "GPT is disabled")
                return
            if len(split_content) > 1:
                await typing(channel_id)
                res_chat = await ask_gpt(" ".join(split_content[1:]))
                if not res_chat:
                    await send_message(channel_id, "GPT Error Fitur di matikan")
                    return
                if len(res_chat) > 2000:
                    for i in await chunks_long_message(res_chat,2000):
                        await send_message(channel_id,i,reply_id=id_message)
                else:
                    await send_message(channel_id,res_chat,reply_id=id_message)
            else:
                await send_message(channel_id, "Please ask something")
                
        elif ">limiter" == content:
            remaining_calls = limiter.get_remaining_calls()
            await send_message(channel_id,f"Sisa pengunaan GPT: {remaining_calls}\nakan reset setelah 1 jam")
        elif ">delete" == content and author == "gingantic":
            # get reply message and get id
            reply_id = message_data['referenced_message']['id']
            await delete_message(channel_id, reply_id)
    except KeyError:
        pass

async def send_message(channel_id, content, reply_id=None):
    print(f'Sending message: {content}')
    #payload for rest api https://discord.com/developers/docs/resources/channel#create-message
    payload = json.loads('{"content": ""}')
    payload['content'] = content
    if reply_id:
        payload.update({"message_reference": {"message_id": reply_id}})
    requests.post(API_URL + f'channels/{channel_id}/messages', headers=HEADER_API, json=payload)

async def edit_message(channel_id, message_id, content):
    print(f'Editing message: {content}')
    payload = json.loads('{"content": ""}')
    payload['content'] = content
    req = requests.patch(API_URL + f'channels/{channel_id}/messages/{message_id}', headers=HEADER_API, json=payload)

async def delete_message(channel_id, message_id):
    req = requests.delete(API_URL + f'channels/{channel_id}/messages/{message_id}', headers=HEADER_API)

async def typing(channel_id):
    requests.post(API_URL + f'channels/{channel_id}/typing', headers=HEADER_API)

async def get_users(username):
    rs = requests.get(API_URL + f'users/{username}', headers=HEADER_API)
    return rs.json()

async def ask_gpt(message):
    global ENABLE_CHAT_GPT
    temp_ask = json.loads('{"role": "user", "content": ""}')
    temp_ask["content"] = message
    await update_dialog_gpt(temp_ask)
    print(json.dumps(CHAT_GPT_DIALOG, indent=4))
    header = {"Content-Type": "application/json"}
    rq = requests.post(CHAT_GPT_ENDPOINT, headers=header, json=CHAT_GPT_DIALOG)
    if rq.status_code != 200:
        ENABLE_CHAT_GPT = False
        await send_message("1028580720655999067", f"Chat GPT error at {get_datetime()}\n{rq.text}")
        return False
    data = rq.json()
    resp = data["choices"][0]["message"]
    content = resp["content"]
    await update_dialog_gpt(resp)
    await save_dialog_gpt()
    print("\n\n"+json.dumps(CHAT_GPT_DIALOG,indent=4))
    return content

async def load_dialog_gpt():
    global CHAT_GPT_DIALOG
    with open(CHAT_GPT_SAVE_PATH, "r") as f:
        CHAT_GPT_DIALOG = json.load(f)

async def save_dialog_gpt():
    with open(CHAT_GPT_SAVE_PATH, "w") as f:
        json.dump(CHAT_GPT_DIALOG, f, indent=4)

async def update_dialog_gpt(data):
    global CHAT_GPT_DIALOG
    CHAT_GPT_DIALOG["messages"].append(data)

async def chunks_long_message(message, max_characters):
    words = message.split()
    chunks = []
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 > max_characters:
            chunks.append(current_chunk.strip())
            current_chunk = ""
        
        current_chunk += word + " "

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

async def main():
    await load_dialog_gpt()
    await connect_to_gateway()

if __name__ == '__main__':
    asyncio.run(main())
    asyncio.run(send_message("1028580720655999067", f"Bot dead at {get_datetime()}"))
