from pkg.plugin.context import EventContext
from typing import Dict, Any, Callable, Awaitable
import inspect

class CommandHandler:
    def __init__(self):
        self.commands: Dict[str, Callable[[EventContext], Awaitable[None]]] = {}
        
    def register(self, command: str, handler: Callable[[EventContext], Awaitable[None]]):
        self.commands[command] = handler
        
    async def handle(self, ctx: EventContext, msg: str) -> bool:
        for cmd, handler in self.commands.items():
            if msg.startswith(cmd):
                await handler(ctx)
                return True
        return False 