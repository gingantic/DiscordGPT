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
ENABLE_COMPRESS = True
# u can change the token.key with token.txt if u want
TOKEN = open("token.key", "r").read().split("\n")[0]
#GATEAWAY_URL = 'wss://gateway.discord.gg/?v=10&encoding=json&compress=zlib-stream'
GATEAWAY_URL = 'wss://gateway.discord.gg/?v=10&encoding=json'
API_URL = 'https://discord.com/api/v10/'
RESUME_STATUS = False
SET_INTENT = 3276799
INTERVAL_HEARTBEAT = None
CHAT_GPT_ENDPOINT = "http://localhost:1337/chat/completions"
CHAT_GPT_DIALOG = None
CHAT_GPT_SAVE_PATH = "historygpt.json"
CHAT_GPT_TEMPLATE_USER = None
ENABLE_CHAT_GPT = True
HEADER_API = {
    "Authorization": TOKEN,
    "Content-Type": "application/json",
    "User-Agent": USER_AGENT
}
WHITE_LIST_CHANNEL = ["1028580720655999067","477911432709799936", "521713650302713869"]
#WHITE_LIST_CHANNEL = []
AUTHOR_USERNAME = "gingantic"
ASYNCLIST = []

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

ZLIB_SUFFIX = b'\x00\x00\xff\xff'
buffer = bytearray()
inflator = zlib.decompressobj()

async def decompress_data(msg):
    global buffer
    try:
        if not msg:
            return None
        buffer.extend(msg)
        if len(msg) < 4 or msg[-4:] != ZLIB_SUFFIX:
            return None
        msg = inflator.decompress(buffer)
        buffer = bytearray()
        return json.loads(msg)
    except Exception as e:
        return None

def get_datetime():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

async def waited_close():
    for task in ASYNCLIST:
        task.cancel()
    asyncio.gather(*ASYNCLIST)

async def connect_to_gateway():
    async with websockets.connect(GATEAWAY_URL) as ws:
        try:
            while ws.open:
                # recv = await ws.recv()
                # payload = await decompress_data(recv)
                payload = json.loads(await ws.recv())
                if not payload:
                    break

                opcode = payload['op']
                seq = payload['s']
                data = payload['d']
                name = payload['t']

                print(f"{get_datetime()} - {opcode}")
                
                if opcode == 10:
                    interval = data['heartbeat_interval'] / 1000
                    ASYNCLIST.append(asyncio.ensure_future(send_heartbeat(ws, interval)))
                    await send_identify(ws)
                elif opcode == 11:
                    print('Heartbeat ACK received')
                elif opcode == 7:
                    print('Reconnect received')
                    await send_message("1028580720655999067", f"OP 7 Reconnect again\nUptime ke - {uptime}")
                    break
                elif opcode == 9:
                    print('Invalid session received')
                    break
                elif opcode == 0:
                    await handle_event(ws, name, data)
                    
        except ConnectionClosedError as e:
            print(f'[{get_datetime()}] Connection error closed with code: {e.code} and reason: {e.reason}')

        except ConnectionClosedOK as e:
            print(f'[{get_datetime()}] Connection closed with code: {e.code} and reason: {e.reason}')

        except Exception as e:
            print(f'[{get_datetime()}] Exception: {e}')
            traceback.print_exc()

        await ws.close()
    await waited_close()


async def send_identify(ws):
    identify_data = {
        "op": 2,
        "d": {
            "token": TOKEN,
            "intents": SET_INTENT,
            "properties": {
                "$os": "linux",
                "$browser": "Gins_app",
                "$device": "Gins_app"
            }
        }
    }
    await ws.send(json.dumps(identify_data))

async def custom_status(ws):
    while ws.open:
        try:
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
            await asyncio.sleep(random.randrange(15, 60))
        except CancelledError:
            break

async def join_voice_channel(ws, channel_id, guild_id):
    payload = {
        "op": 4,
        "d": {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "self_mute": False,
            "self_deaf": True
        }
    }
    await ws.send(json.dumps(payload))

async def leave_voice_channel(ws, channel_id, guild_id):
    payload = {
        "op": 4,
        "d": {
            "guild_id": guild_id,
            "channel_id": None,
            "self_mute": False,
            "self_deaf": False
        }
    }
    await ws.send(json.dumps(payload))

async def speak_voice_channel(ws, guild_id, audio):
    # what the audio
    # audio = "data:audio/ogg;base64," + base64.b64encode(audio).decode('utf-8')
    payload = {
        "op": 5,
        "d": {
            "guild_id": guild_id,
            "audio": audio
        }
    }
    await ws.send(json.dumps(payload))

async def send_heartbeat(ws, interval):
    while ws.open:
        try:
            await asyncio.sleep(interval)
            payload = {
                'op': 1,
                'd': None
            }
            await ws.send(json.dumps(payload))
        except CancelledError:
            break

async def handle_event(ws, event_type, event_data):
    global USERNAME_BOT
    if event_type == 'READY':
        print('Ready event received')
        USERNAME_BOT = event_data['user']['username']
        print(USERNAME_BOT)
        ASYNCLIST.append(asyncio.ensure_future(custom_status(ws)))
        await send_message("1028580720655999067", f"Bot lauched")

    elif event_type == 'MESSAGE_CREATE':
        await handle_message(ws, event_data)

async def handle_message(ws, message_data):
    try:
        message_id = message_data['id']
        author = message_data['author']['username']
        name = message_data['author']['global_name']
        mention_id = message_data['mentions']
        first_mention = None
        content = message_data['content']
        channel_id = message_data['channel_id']
        split_content = content.split(" ")
        guild_id = message_data['guild_id']
        for i in mention_id:
            if i['username'] == USERNAME_BOT:
                first_mention = i
                break
        if not channel_id in WHITE_LIST_CHANNEL:
            return
        if author == "gingantic":
            print(message_data)
        # if USERNAME_BOT in str(message_data['mentions']):
        #     await send_message(channel_id, f"Halo {name}!", reply_id=message_data['id'])
        if ">uptime" == content:
            uptime_time = time.time() - uptime
            uptime_time_format = str(datetime.timedelta(seconds=uptime_time)).split(".")[0]
            await send_message(channel_id, f"Uptime: {uptime_time_format}")
        elif ">ping" == content:
            await send_message(channel_id, "Pong!")
        elif ">chat_disable" == content and author == "gingantic":
            await gpt_status(channel_id, False)
        elif ">chat_enable" == content and author == "gingantic":
            await gpt_status(channel_id, True)
        elif split_content[0] in [">chat",">ask",">askchat"]:
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
                    for i in chunks_long_message(res_chat,2000):
                        await send_message(channel_id,i,reply_id=message_id)
                else:
                    await send_message(channel_id,res_chat,reply_id=message_id)
            else:
                await send_message(channel_id, "Please ask something")
        elif ">limiter" == content:
            remaining_calls = limiter.get_remaining_calls()
            await send_message(channel_id,f"Sisa pengunaan GPT: {remaining_calls}\nakan reset setelah 1 jam")
        elif ">delete" == content and author == "gingantic":
            reply_id = message_data['referenced_message']['id']
            await delete_message(channel_id, reply_id)
        elif ">reload_dialog" == content and author == "gingantic":
            load_dialog_gpt()
            await send_message(channel_id, "Dialog reloaded")
        elif ">change_model" in content and author == "gingantic":
            model_name = content.split(" ")[1]
            if CHAT_GPT_DIALOG['model'] == model_name:
                await send_message(channel_id, "Model sama")
                return
            else:
                CHAT_GPT_DIALOG['model'] = model_name
                save_dialog_gpt()
                await send_message(channel_id, f"Model changed to {model_name}")
        elif split_content[0] in ">join_vc" and author == "gingantic":
            if len(split_content) < 2:
                await send_message(channel_id, "Please provide channel id")
                return
            await join_voice_channel(ws, split_content[1], guild_id)
        elif split_content[0] in ">leave_vc" and author == "gingantic":
            await leave_voice_channel(ws, channel_id, guild_id)
    except KeyError:
        pass

async def gpt_status(channel_id, status: bool):
    global ENABLE_CHAT_GPT
    ENABLE_CHAT_GPT = status
    if status:
        await send_message(channel_id, "GPT is Enabled")
    else:
        await send_message(channel_id, "GPT is Disabled")

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
    update_dialog_gpt(temp_ask)
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
    update_dialog_gpt(resp)
    save_dialog_gpt()
    print("\n\n"+json.dumps(CHAT_GPT_DIALOG,indent=4))
    return content

def load_dialog_gpt():
    global CHAT_GPT_DIALOG
    with open(CHAT_GPT_SAVE_PATH, "r") as f:
        CHAT_GPT_DIALOG = json.load(f)

def save_dialog_gpt():
    with open(CHAT_GPT_SAVE_PATH, "w") as f:
        json.dump(CHAT_GPT_DIALOG, f, indent=4)

def update_dialog_gpt(data):
    global CHAT_GPT_DIALOG
    CHAT_GPT_DIALOG["messages"].append(data)

def chunks_long_message(message, max_characters):
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
    try:
        await connect_to_gateway()
    except:
        pass

if __name__ == '__main__':
    load_dialog_gpt()
    while True:
        asyncio.run(main())
        print("Reconnecting in 2 seconds")
        time.sleep(2)