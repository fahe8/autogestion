from src.generated import Prisma


prisma = Prisma()


async def connect_db() -> None:
    await prisma.connect()


async def disconnect_db() -> None:
    await prisma.disconnect()
