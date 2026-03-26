import asyncio
import time

from robyn import Robyn, SSEMessage, SSEResponse, html

app = Robyn(__file__)

@app.post("/events/async")
async def stream_async_events(request):
    async def async_event_generator():
        for i in range(8):
            # Simulate async work
            await asyncio.sleep(0.5)
            yield SSEMessage(f"Async message {i} - {time.strftime('%H:%M:%S')}", event="message_chunk", id=str(i))

    return SSEResponse(async_event_generator())



if __name__ == "__main__":
        app.start(host="0.0.0.0", port=8080)