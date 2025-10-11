import asyncio
import signal
import time

from rich.live import Live
from rich.table import Table


async def fetch_videos(queue):
    i = 0
    while True:
        item = {"i": i, "cur_time": time.time()}
        await queue.put(item)
        i += 1
        await asyncio.sleep(0.1)


async def get_multiple_items(queue, num_items):
    items = []
    for _ in range(num_items):
        item = await queue.get()
        items.append(item)
    return items


async def measure_happiness(queue_in, queue_out):
    while True:
        item_list = await get_multiple_items(queue_in, 2)
        for item in item_list:
            await queue_out.put(item)


async def improve_descriptions(queue):
    while True:
        item_list = await get_multiple_items(queue, 2)
        # for item in item_list:
        # print(item)


async def queue_info(queue1, queue2):
    with Live(refresh_per_second=1) as live:
        while True:
            table = Table(title="Queue Sizes")
            table.add_column("Queue", justify="right", style="cyan", no_wrap=True)
            table.add_column("Size", style="magenta")

            table.add_row("queue1", str(queue1.qsize()))
            table.add_row("queue2", str(queue2.qsize()))

            live.update(table)
            await asyncio.sleep(1)


def signal_handler(loop):
    for task in asyncio.all_tasks(loop):
        task.cancel()


async def main():
    # config_queue = asyncio.Queue()
    queue1 = asyncio.Queue()
    queue2 = asyncio.Queue()
    await asyncio.gather(
        queue_info(queue1, queue2),
        fetch_videos(queue1),
    )
    await asyncio.sleep(5)  # Delay for 5 seconds

    await asyncio.gather(
        measure_happiness(queue1, queue2),
        improve_descriptions(queue2),
    )


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: signal_handler(loop))
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
