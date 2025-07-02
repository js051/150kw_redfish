from flask import Flask, Response, request, abort
import json, threading, queue, time
from functools import lru_cache


event_queue = queue.Queue()

def event_producer():
    """示範：每 5 秒產生一筆測試事件"""
    i = 0
    while True:
        time.sleep(5)
        evt = {
            "EventType": "TestEvent",
            "EventId": f"EVT{i}",
            "Message": f"Test message {i}",
            "EventTimestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        event_queue.put(evt)
        i += 1

@lru_cache(maxsize=1)
def start_SSE_threading():
    # 背景執行事件產生
    threading.Thread(target=event_producer, daemon=True, name="SSE_threads").start()

def event_stream(Enabled: bool, filters=None):
    start_SSE_threading()
    # threading.Thread(target=event_producer, daemon=True, name="SSE_threads").start()
    # print("Enabled:", Enabled)
    while True:
        evt = event_queue.get()    # 阻塞等待新事件
        # 依需實作過濾邏輯：if not match(filters, evt): continue
        # if filters and evt.get("EventType") not in filters.get("EventTypes", []):
        #     continue
        if Enabled is True:
            print("enabled")
            # 送出 SSE 格式：event + data + blank line
            yield f"event: {evt['EventType']}\n"
            yield "data: " + json.dumps(evt) + "\n\n"
        else:
            print("disabled")
            continue    


