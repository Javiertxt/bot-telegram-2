import logging
from telegram import Bot, Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
import pytz
import os
from datetime import datetime

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Obtener el token desde las variables de entorno
TOKEN = os.getenv('YOUR_BOT_API_TOKEN')

CHANNEL, NAME, TITLE, DESCRIPTION, COUPON, OFFER_PRICE, OLD_PRICE, LINK, IMAGE, SCHEDULE_OPTION, SCHEDULE = range(11)

scheduled_posts = []

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
        update.message.reply_text('¿Quieres publicar al instante o programar la publicación? Responde "instante" o "programar".')
        return SCHEDULE_OPTION
    elif update.message.text:
        context.user_data['image'] = update.message.text
        context.user_data['image_type'] = 'link'
        update.message.reply_text('¿Quieres publicar al instante o programar la publicación? Responde "instante" o "programar".')
        return SCHEDULE_OPTION
    else:
        update.message.reply_text('Por favor, envía una imagen válida o un enlace de imagen.')
        return IMAGE

def get_schedule_option(update: Update, context: CallbackContext) -> int:
    if update.message.text.lower() == 'instante':
        schedule_post(context.user_data, immediate=True)
        update.message.reply_text('La publicación se ha realizado inmediatamente.')
        return ConversationHandler.END
    elif update.message.text.lower() == 'programar':
        now = datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M')
        update.message.reply_text(f'Por favor, proporciona la fecha y hora de la publicación en formato YYYY-MM-DD HH:MM. Hora actual: {now}')
        return SCHEDULE
    else:
        update.message.reply_text('Por favor, responde "instante" o "programar".')
        return SCHEDULE_OPTION

def set_schedule(update: Update, context: CallbackContext) -> int:
    try:
        schedule_time = datetime.strptime(update.message.text, '%Y-%m-%d %H:%M')
        context.user_data['schedule'] = schedule_time
        scheduled_posts.append(context.user_data)
        schedule_post(context.user_data)
        update.message.reply_text('La publicación ha sido programada.')
        return ConversationHandler.END
    except ValueError:
        update.message.reply_text('Formato de fecha y hora inválido. Por favor, inténtalo de nuevo en formato YYYY-MM-DD HH:MM.')

def schedule_post(data, immediate=False):
    bot = Bot(token=TOKEN)
    text = f"<b><a href='{data['link']}'>{data['name']}</a></b>\n" \
           f"<b>{data['title']}</b>\n\n" \
           f"{data['description']}\n\n" \
           f"<b>➡️CUPÓN: {data['coupon']}</b>\n" \
           f"<b>✅OFERTA: {data['offer_price']}</b>\n" \
           f"<b>❌ANTES: <s>{data['old_price']}</s></b>\n\n" \
           f"{data['link']}\n\n"
    if data['image_type'] == 'file':
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
    elif data['image_type'] == 'link':
        if immediate:
            bot.send_message(chat_id=data['channel'], text=text + f"<a href='{data['image']}'>\u200C</a>", parse_mode=ParseMode.HTML)
        else:
            trigger = DateTrigger(run_date=data['schedule'], timezone=pytz.utc)
            scheduler.add_job(bot.send_message, trigger, kwargs={
                'chat_id': data['channel'],
                'text': text + f"<a href='{data['image']}'>\u200C</a>",
                'parse_mode': ParseMode.HTML
            })

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Operación cancelada.')
    return ConversationHandler.END

def view_scheduled(update: Update, context: CallbackContext) -> None:
    if scheduled_posts:
        for i, post in enumerate(scheduled_posts):
            update.message.reply_text(f"{i + 1}. {post['title']} programado para {post['schedule']}")
    else:
        update.message.reply_text('No hay publicaciones programadas.')

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

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        "/start - Comenzar una nueva publicación\n"
        "/view - Ver publicaciones programadas\n"
        "/delete - Eliminar una publicación programada\n"
        "/cancel - Cancelar la operación actual\n"
        "/help - Mostrar este mensaje de ayuda"
    )

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    global scheduler
    scheduler = BackgroundScheduler()
    scheduler.start()

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
            IMAGE: [MessageHandler(Filters.photo | Filters.text & ~Filters.command, get_image)],
            SCHEDULE_OPTION: [MessageHandler(Filters.text & ~Filters.command, get_schedule_option)],
            SCHEDULE: [MessageHandler(Filters.text & ~Filters.command, set_schedule)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler('view', view_scheduled))
    dispatcher.add_handler(CommandHandler('delete', delete_scheduled))
    dispatcher.add_handler(CommandHandler('help', help_command))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
