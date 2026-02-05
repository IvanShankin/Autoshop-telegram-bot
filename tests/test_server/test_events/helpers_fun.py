import asyncio

import aio_pika


async def wait_until_queue_empty(
    channel: aio_pika.Channel,
    queue_name: str,
    timeout: float = 5.0,
):
    deadline = asyncio.get_running_loop().time() + timeout

    while True:
        queue = await channel.declare_queue(queue_name, passive=True)

        if queue.declaration_result.message_count == 0:
            return

        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError(f"Queue {queue_name} not empty")

        await asyncio.sleep(0.05)
