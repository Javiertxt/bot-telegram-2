import logging
from telegram import Bot, Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz

# Configuración básica de logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

# Definición de constantes para los estados del conversacional
NAME, TITLE, DESCRIPTION, COUPON, OFFER_PRICE, OLD_PRICE, LINK, IMAGE, CHANNEL, SCHEDULE = range(10)

# Diccionario para almacenar las publicaciones programadas
scheduled_posts = []

# Función para iniciar el bot
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('¡Hola! Vamos a crear una nueva publicación.\nPor favor, dime el nombre de la tienda.')
    return NAME

# Función para recibir y almacenar el nombre de la tienda
def get_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text('Ahora, por favor dime el título del producto.')
    return TITLE

# Funciones para recibir y almacenar los otros datos
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
    update.message.reply_text('Por favor, proporciona la imagen del producto.')
    return IMAGE

def get_image(update: Update, context: CallbackContext) -> int:
    context.user_data['image'] = update.message.photo[-1].get_file().file_id
    update.message.reply_text('¿En qué canal quieres publicar? Por favor, proporciona el ID del canal.')
    return CHANNEL

def get_channel(update: Update, context: CallbackContext) -> int:
    context.user_data['channel'] = update.message.text
    update.message.reply_text('¿Quieres programar la publicación? Responde "sí" o "no".')
    return SCHEDULE

def get_schedule(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'sí':
        update.message.reply_text('Por favor, proporciona la fecha y hora de la publicación en formato YYYY-MM-DD HH:MM.')
    else:
        context.user_data['schedule'] = None
        schedule_post(context.user_data, immediate=True)
        update.message.reply_text('La publicación se ha realizado inmediatamente.')
        return ConversationHandler.END

def schedule_post(data, immediate=False):
    bot = Bot(token='YOUR_BOT_API_TOKEN')
    text = f"<b><a href='{data['link']}'>{data['name']}</a></b>\n" \
           f"<b>{data['title']}</b>\n\n" \
           f"{data['description']}\n\n" \
           f"<b>➡️CUPÓN: {data['coupon']}</b>\n" \
           f"<b>✅OFERTA: {data['offer_price']}</b>\n" \
           f"<b>❌ANTES: <s>{data['old_price']}</s></b>\n\n" \
           f"{data['link']}\n\n"
    if immediate:
        bot.send_photo(chat_id=data['channel'], photo=data['image'], caption=text, parse_mode=ParseMode.HTML)
    else:
        trigger = DateTrigger(run_date=data['schedule'], timezone=pytz.utc)
        scheduler.add_job(bot.send_photo, trigger, kwargs={
            'chat_id': data['channel'],
            'photo': data['image'],
            'caption': text,
            'parse_mode': ParseMode.HTML
        })

def set_schedule(update: Update, context: CallbackContext) -> int:
    from datetime import datetime
    try:
        schedule_time = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        context.user_data['schedule'] = schedule_time
        scheduled_posts.append(context.user_data)
        schedule_post(context.user_data)
        update.message.reply_text('La publicación ha sido programada.')
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text('Formato de fecha y hora inválido. Por favor, inténtalo de nuevo en formato YYYY-MM-DD HH:MM.')

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Operación cancelada.')
    return ConversationHandler.END

# Configuración del comando para revisar publicaciones programadas
def view_scheduled(update: Update, context: CallbackContext) -> None:
    if scheduled_posts:
        for i, post in enumerate(scheduled_posts):
            update.message.reply_text(f"{i + 1}. {post['title']} programado para {post['schedule']}")
    else:
        update.message.reply_text('No hay publicaciones programadas.')

# Configuración del comando para eliminar publicaciones programadas
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

# Configuración del manejador del bot y del programador de tareas
def main():
    updater = Updater(token='YOUR_BOT_API_TOKEN', use_context=True)
    dispatcher = updater.dispatcher
    global scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, get_name)],
            TITLE: [MessageHandler(Filters.text & ~Filters.command, get_title)],
            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, get_description)],
            COUPON: [MessageHandler(Filters.text & ~Filters.command, get_coupon)],
            OFFER_PRICE: [MessageHandler(Filters.text & ~Filters.command, get_offer_price)],
            OLD_PRICE: [MessageHandler(Filters.text & ~Filters.command, get_old_price)],
            LINK: [MessageHandler(Filters.text & ~Filters.command, get_link)],
            IMAGE: [MessageHandler(Filters.photo & ~Filters.command, get_image)],
            CHANNEL: [MessageHandler(Filters.text & ~Filters.command, get_channel)],
            SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, get_schedule)],
            'SET_SCHEDULE': [MessageHandler(Filters.text & ~Filters.command, set_schedule)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('view', view_scheduled))
    dispatcher.add_handler(CommandHandler('delete', delete_scheduled))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
