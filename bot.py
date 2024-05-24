import logging
from telegram import Bot, Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, Dispatcher
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz
import os
from datetime import datetime, timedelta
from flask import Flask, request
from telegram.error import RetryAfter, NetworkError, TelegramError
import time

# Configurar el logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('YOUR_BOT_API_TOKEN')
HEROKU_APP_NAME = os.getenv('HEROKU_APP_NAME')

CHANNEL, NAME, TITLE, DESCRIPTION, COUPON, OFFER_PRICE, OLD_PRICE, LINK, IMAGE, SCHEDULE_OPTION, SCHEDULE = range(11)

scheduled_posts = []

# Crear la aplicación Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running"

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# Funciones del bot de Telegram
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('¡Hola! Vamos a crear una nueva publicación.\nPor favor, dime el ID del canal donde deseas publicar.')
    return CHANNEL

def get_channel(update: Update, context: CallbackContext) -> int:
    context.user_data['channel'] = update.message.text
    update.message.reply_text('Por favor, dime el nombre de la tienda.')
    return NAME

def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text('Ahora, por favor dime el título del producto.')
    return TITLE

def get_title(update: Update, context: CallbackContext) -> int:
    context.user_data['title'] = update.message.text
    update.message.reply_text('Por favor, dime la descripción del producto.')
    return DESCRIPTION

def get_description(update: Update, context: CallbackContext) -> int:
    context.user_data['description'] = update.message.text
    update.message.reply_text('¿Cuál es el cupón de descuento?')
    return COUPON

def get_coupon(update: Update, context: CallbackContext) -> int:
    context.user_data['coupon'] = update.message.text
    update.message.reply_text('¿Cuál es el precio de oferta?')
    return OFFER_PRICE

def get_offer_price(update: Update, context: CallbackContext) -> int:
    context.user_data['offer_price'] = update.message.text
    update.message.reply_text('¿Cuál era el precio anterior?')
    return OLD_PRICE

def get_old_price(update: Update, context: CallbackContext) -> int:
    context.user_data['old_price'] = update.message.text
    update.message.reply_text('Por favor, proporciona el enlace del producto.')
    return LINK

def get_link(update: Update, context: CallbackContext) -> int:
    context.user_data['link'] = update.message.text
    update.message.reply_text('Por favor, envía la imagen del producto o el enlace de la imagen.')
    return IMAGE

def get_image(update: Update, context: CallbackContext) -> int:
    if update.message.photo:
        context.user_data['image'] = update.message.photo[-1].get_file().file_id
        context.user_data['image_type'] = 'file'
    elif update.message.text:
        context.user_data['image'] = update.message.text
        context.user_data['image_type'] = 'link'
    else:
        update.message.reply_text('Por favor, envía una imagen válida o un enlace de imagen.')
        return IMAGE

    text = generate_post_text(context.user_data)
    update.message.reply_text(f'Previsualización de la publicación:\n\n{text}', parse_mode=ParseMode.HTML)
    update.message.reply_text('¿Quieres publicar ahora o programar la publicación? Responde "ahora" o "programar".')
    return SCHEDULE_OPTION

def get_schedule_option(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'ahora':
        schedule_post(context.user_data, immediate=True)
        update.message.reply_text('La publicación se ha realizado inmediatamente.')
        return ConversationHandler.END
    elif update.message.text.lower() == 'programar':
        now = datetime.now(pytz.timezone('Europe/Madrid')).strftime('%Y-%m-%d %H:%M')
        update.message.reply_text(f'Por favor, proporciona la fecha y hora de la publicación en formato YYYY-MM-DD HH:MM. Hora actual: {now}')
        return SCHEDULE
    else:
        update.message.reply_text('Por favor, responde "ahora" o "programar".')
        return SCHEDULE_OPTION

def set_schedule(update: Update, context: CallbackContext) -> int:
    try:
        schedule_time = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        schedule_time = pytz.timezone('Europe/Madrid').localize(schedule_time)
        context.user_data['schedule'] = schedule_time
        scheduled_posts.append(context.user_data.copy())
        schedule_post(context.user_data)
        update.message.reply_text('La publicación ha sido programada.')
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text('Formato de fecha y hora inválido. Por favor, inténtalo de nuevo en formato YYYY-MM-DD HH:MM.')

def post_publication(bot, job):
    data = job.context
    text = generate_post_text(data)
    try:
        if data['image_type'] == 'file':
            bot.send_photo(chat_id=data['channel'], photo=data['image'], caption=text, parse_mode=ParseMode.HTML)
        elif data['image_type'] == 'link':
            bot.send_message(chat_id=data['channel'], text=text + f"<a href='{data['image']}'>\u200C</a>", parse_mode=ParseMode.HTML)
        scheduled_posts.remove(data)
    except RetryAfter as e:
        logger.warning(f"Flood control exceeded. Retry in {e.retry_after} seconds.")
        job.reschedule(DateTrigger(run_date=datetime.now(pytz.utc) + timedelta(seconds=e.retry_after)))
    except NetworkError as e:
        logger.error(f"Network error occurred: {e}. Rescheduling job.")
        job.reschedule(DateTrigger(run_date=datetime.now(pytz.utc) + timedelta(seconds=60)))
    except TelegramError as e:
        logger.error(f"Telegram error occurred: {e}.")
    except Exception as e:
        logger.error(f"Unexpected error occurred: {e}.")

def schedule_post(data, immediate=False):
    bot = Bot(token=TOKEN)
    text = generate_post_text(data)
    
    if immediate:
        try:
            if data['image_type'] == 'file':
                bot.send_photo(chat_id=data['channel'], photo=data['image'], caption=text, parse_mode=ParseMode.HTML)
            elif data['image_type'] == 'link':
                bot.send_message(chat_id=data['channel'], text=text + f"<a href='{data['image']}'>\u200C</a>", parse_mode=ParseMode.HTML)
        except RetryAfter as e:
            logger.warning(f"Flood control exceeded. Retry in {e.retry_after} seconds.")
            time.sleep(e.retry_after)
            schedule_post(data, immediate=True)
        except NetworkError as e:
            logger.error(f"Network error occurred: {e}. Retrying in 60 seconds.")
            time.sleep(60)
            schedule_post(data, immediate=True)
        except TelegramError as e:
            logger.error(f"Telegram error occurred: {e}.")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}.")
    else:
        trigger = DateTrigger(run_date=data['schedule'], timezone=pytz.utc)
        job = scheduler.add_job(post_publication, trigger, args=[bot], context=data)

def generate_post_text(data):
    return (f"<b><a href='{data['link']}'>{data['name']}</a></b>\n\n"
            f"<b>{data['title']}</b>\n\n"
            f"{data['description']}\n\n"
            f"<b>➡️CUPÓN: {data['coupon']}</b>\n\n"
            f"<b>✅OFERTA: {data['offer_price']}</b>\n\n"
            f"<b>❌ANTES: <s>{data['old_price']}</s></b>\n\n"
            f"{data['link']}")

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Operación cancelada.')
    return ConversationHandler.END

def view_scheduled(update: Update, context: CallbackContext) -> None:
    if not scheduled_posts:
        update.message.reply_text('No hay publicaciones programadas.')
    else:
        message = 'Publicaciones programadas:\n'
        for i, post in enumerate(scheduled_posts, 1):
            message += f"{i}. {post['title']} - {post['schedule']}\n"
        update.message.reply_text(message)

def delete_scheduled(update: Update, context: CallbackContext) -> None:
    try:
        index = int(update.message.text.split()[1]) - 1
        if 0 <= index < len(scheduled_posts):
            del scheduled_posts[index]
            update.message.reply_text('Publicación eliminada.')
        else:
            update.message.reply_text('Índice inválido.')
    except (IndexError, ValueError):
        update.message.reply_text('Por favor, proporciona el índice de la publicación a eliminar, por ejemplo: /delete 1')

def edit_scheduled(update: Update, context: CallbackContext) -> None:
    try:
        index = int(update.message.text.split()[1]) - 1
        if 0 <= index < len(scheduled_posts):
            context.user_data.update(scheduled_posts[index])
            del scheduled_posts[index]
            update.message.reply_text('Vamos a editar la publicación. Proporciona los nuevos datos.')
            return TITLE
        else:
            update.message.reply_text('Índice inválido.')
    except (IndexError, ValueError):
        update.message.reply_text('Por favor, proporciona el índice de la publicación a editar, por ejemplo: /edit 1')

    return ConversationHandler.END

# Inicializar el bot y el dispatcher
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# Configurar los manejadores del bot
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHANNEL: [MessageHandler(Filters.text & ~Filters.command, get_channel)],
        NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
        TITLE: [MessageHandler(Filters.text & ~Filters.command, get_title)],
        DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, get_description)],
        COUPON: [MessageHandler(Filters.text & ~Filters.command, get_coupon)],
        OFFER_PRICE: [MessageHandler(Filters.text & ~Filters.command, get_offer_price)],
        OLD_PRICE: [MessageHandler(Filters.text & ~Filters.command, get_old_price)],
        LINK: [MessageHandler(Filters.text & ~Filters.command, get_link)],
        IMAGE: [MessageHandler(Filters.text & ~Filters.command, get_image)],
        SCHEDULE_OPTION: [MessageHandler(Filters.text & ~Filters.command, get_schedule_option)],
        SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, set_schedule)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CommandHandler('view', view_scheduled))
dispatcher.add_handler(CommandHandler('delete', delete_scheduled))
dispatcher.add_handler(CommandHandler('edit', edit_scheduled))

scheduler = BackgroundScheduler(timezone=pytz.utc)
scheduler.start()

# Configurar el webhook de Telegram
bot.set_webhook(f"https://{HEROKU_APP_NAME}.herokuapp.com/{TOKEN}")

if __name__ == '__main__':
    from os import environ
    PORT = int(environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=PORT)
