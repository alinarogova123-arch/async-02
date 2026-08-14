import asyncio
import logging
import os
import aiofiles
import aiohttp
from aiohttp import web
from environs import Env


logger = logging.getLogger(__name__)


async def archive(request):
    path = request.app['path']
    delay = request.app['delay']
    archive_hash = request.match_info.get('archive_hash', "Anonymous")
    cwd = f'{path}/{archive_hash}/'

    if not os.path.exists(cwd):
        raise web.HTTPNotFound(text="Архив не найден")

    response = web.StreamResponse()
    response.headers['Content-Type'] = 'application/zip'
    response.headers['Content-Disposition'] = 'attachment; filename="photos.zip"'

    await response.prepare(request)

    cmd = ['zip', '-r', '-q', '-', '.']

    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
    )

    try:
        while True:
            chunk = await process.stdout.read(512000)
            if not chunk:
                break
            await response.write(chunk)
            logger.info( u'Sending archive chunk ...' )
            if delay:
                await asyncio.sleep(delay)
    except (asyncio.CancelledError, aiohttp.client_exceptions.ClientConnectionResetError):
        logger.error( u'Download was interrupted' )
        raise
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()

    return response


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    env = Env()
    env.read_env()
    app = web.Application()
    if env.bool('ENABLE_LOGGING', default=True):
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)
    app['path'] = env.str('PHOTOS_DIR', default='test_photos')
    app['delay'] = env.float('DELAY', default=0.0)
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
