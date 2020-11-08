import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Message, ForceReply, Bot, Chat, \
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import CallbackContext, Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from emoji import emojize
from datetime import timedelta, datetime
from stundenplan import Stundenplan
from vertretungsplan import Vertretungsplan
import logging
from os import chdir

ARROW_LEFT = emojize(":arrow_backward:", use_aliases=True)
ARROW_RIGHT = emojize(":arrow_forward:", use_aliases=True)
EMOJI_NEW = emojize(":new:", use_aliases=True)
EMOJI_SAD = emojize(":confused:", use_aliases=True)

ADMINS = ["johanneslin"]


def plan(update: Update, context: CallbackContext):
    send_plan(update.message.from_user.username, update.effective_chat, new_plan=True)


def send_plan(username, chat: Chat, new_plan=True, message: Message = None, date: datetime = datetime.today()):
    if date.weekday() > 4:
        date += timedelta(days=2)

    def date_to_name(_date):
        return ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag")[date.weekday()]

    def construct_message(day, _substitution, _date):
        msg = "```"
        msg += f'  {date_to_name(_date).ljust(10)}  {_date.strftime("%d-%m-%y")}'
        for row in range(len(day)):  # for every lesson
            if day[row] != "---":  # if day not empty
                msg += f'\n{row + 1}  '
                msg += f"{day[row].split(' ')[1].split('-')[0].rjust(3)} "
                msg += f"{day[row].split(' ')[2].ljust(4)} "
                msg += f"{day[row].split(' ')[3]} "

                # add substitution plan infos
                # possible types: Vertr. | Verlegung | Raum | Vtr. | enfälllt | EVA | Betreuung | Unterricht geändert
                for entry in _substitution:
                    if entry["subject"] == day[row].split(" ")[1]:  # if substitution matches a subject
                        if entry["type"] == "entfälllt":
                            msg += f"-> Entfall"
                        else:
                            msg += f"-> "
                            if entry["teacher"] != day[row].split(" ")[2]:
                                msg += f"{entry['teacher']} "
                            if entry["room"] != day[row].split(" ")[3]:
                                msg += f"{entry['room']} "
                        break
            else:
                msg += f'\n{row + 1}'
        msg += "```"
        return msg

    name = load_userdata()[username][0]
    if name == "":
        message.reply_text("Bitte gib mir die Login-Daten für deinen Stundenplan. (Nachname)",
                           reply_markup=ForceReply())
        return

    splan = Stundenplan(name)
    vplan = Vertretungsplan().get_filtered(splan)
    if date.strftime("%d-%m-%y") in vplan:  # get only substitution info for that date
        substitution = vplan[date.strftime("%d-%m-%y")]
    else:  # empty list if none
        substitution = []

    new_message = construct_message(splan.get_day(date), substitution, date)

    # inline keyboard date already contains date for previous and next plans
    next_date = (date + timedelta(days=1))
    prev_date = (date - timedelta(days=1))
    if next_date.weekday() == 5:
        next_date += timedelta(days=2)
    if prev_date.weekday() == 6:
        prev_date -= timedelta(days=2)

    reply_markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(ARROW_LEFT, callback_data=f'plan {prev_date.strftime("%d-%m-%y")}'),
        InlineKeyboardButton(ARROW_RIGHT, callback_data=f'plan {next_date.strftime("%d-%m-%y")}')
    ]])
    if new_plan:
        chat.send_message(new_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        add_admin_log(f"Sent plan to @{username}, date={date.strftime('%d-%m-%y')}.")
    else:
        message.edit_text(new_message, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
        add_admin_log(f"Sent plan to @{username}, date={date.strftime('%d-%m-%y')}.")


def start(update: Update, context: CallbackContext):
    userdata = load_userdata()
    username = update.effective_user.username
    if username in userdata:
        userdata[username][1] = update.effective_chat.id
    else:
        add_admin_log(f"New user: username='@{username}', chat_id='{update.effective_chat.id}'.")
        userdata[username] = ["", update.effective_chat.id]
    save_userdata(userdata)
    change_name(update, context)


def change_name(update: Update, context: CallbackContext):
    username = update.effective_user.username
    userdata = load_userdata()

    # check if user already has a login
    if username in userdata and userdata[username][0] != "":  # login available
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("ändern", callback_data='change_login')
        ]])
        update.message.reply_text(f"Dein aktueller Login ist: {userdata[username][0]}", reply_markup=reply_markup)

    else:  # no login available
        userdata[username] = ["", update.effective_chat.id]
        update.message.reply_text(f"Du hast mir noch keine Login-Daten angegeben.")
        save_userdata(userdata)
        update.message.reply_text("Bitte gib mir die Login-Daten für deinen Stundenplan. (Nachname)",
                                  reply_markup=ForceReply())


def message_update(update: Update, context: CallbackContext):
    userdata = load_userdata()
    username = update.effective_user.username
    add_admin_log(f"Received message from @{username}: \"{update.message.text}\"")
    if username in userdata and userdata[username][0] == "":
        name = update.message.text.split(" ")[0].lower()
        # check if valid
        valid = True
        if not 1 < len(name) < 20:
            valid = False
        for char in name:
            if char not in "abcdefghijklmnopqrstuvwxyz1234567890öäü":
                valid = False

        check, check_dbidx = Stundenplan.check_name(name)
        if not valid:
            update.message.reply_text(f"Der Name darf nur Buchstaben und Zahlen von 0 bis 9 enthalten.")
            update.message.reply_text("Bitte gib mir die Login-Daten für deinen Stundenplan. (Nachname)",
                                      reply_markup=ForceReply())
        elif not check:
            update.message.reply_text(f"Der Name {name} ist nicht gültig.")
            update.message.reply_text("Bitte gib mir die Login-Daten für deinen Stundenplan. (Nachname)",
                                      reply_markup=ForceReply())

        elif len(check) > 1:
            keyboard = []
            for i in range(len(check)):
                keyboard.append([InlineKeyboardButton(str(check[i]), callback_data=f"name {name} {check_dbidx[i]}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text("Es wurden mehrere Einträge gefunden, bitte wähle.",
                                      reply_markup=reply_markup)

        elif check == [name]:
            userdata[username][0] = [name, 0]
            save_userdata(userdata)
            add_admin_log(f"Name for @{username} set to '{[name, 0]}'.")
            update.message.reply_text(f"Dein Name wurde als \"{name}\" gespeichert.\n"
                                      f"Du kannst ihn jederzeit mit /name ändern.")
            send_plan(username, update.effective_chat, new_plan=True)
        else:
            raise ValueError(f"Name {name} was not handled check={check}")


def save_userdata(data):
    with open("userdata.json", "w") as f:
        f.write(json.dumps(data))


def load_userdata():
    with open("userdata.json", "r") as f:
        text = f.read()
        return json.loads(text)


def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    userdata = load_userdata()
    username = query.from_user.username

    # check which button was pressed
    if query.data == "change_login":
        userdata[username][0] = ""
        save_userdata(userdata)
        query.message.reply_text("Bitte gib mir die Login-Daten für deinen Stundenplan. (Nachname)",
                                 reply_markup=ForceReply())
    elif query.data[:4] == "plan":
        if len(query.data) == 4:  # new plan
            send_plan(query.from_user.username, query.message.chat, new_plan=True)
        else:  # edit plan
            new_date = datetime.strptime(query.data.split(" ")[1], "%d-%m-%y")
            send_plan(query.from_user.username, query.message.chat, new_plan=False, message=query.message,
                      date=new_date)
    elif query.data[:4] == "name":
        print(query.data)
        name = (query.data.split(" ")[1], "".join(query.data.split(" ")[2]))
        userdata[username][0] = name
        save_userdata(userdata)
        add_admin_log(f"Name for @{username} set to '{name}'.")
        update.effective_chat.send_message(f"Dein Name wurde als \"{name[0]}\" gespeichert.\n"
                                  f"Du kannst ihn jederzeit mit /name ändern.")
        send_plan(username, update.effective_chat, new_plan=True)


def author(update: Update, context: CallbackContext):
    update.message.reply_text("__LLG Vertretungsplan__\n"
                              "Autor: Johannes Lingk\n"
                              "Email: johannes\.lingk@gmail\.com",
                              reply_markup=ReplyKeyboardRemove(),
                              parse_mode=ParseMode.MARKDOWN_V2)


def add_admin_log(*msg):
    message = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    for m in msg:
        message += " - " + str(m)
    message = message.strip() + "\n"
    with open("admin.log", "a+") as f:
        print(message.strip("\n"))
        f.write(message)


def admin_help(update: Update, context: CallbackContext):
    if update.effective_user.username not in ADMINS: return
    text = """Admin Commands:
    /admin_help - Displays this help message.
    /admin_get_users - Get a list of all users using this bot.
    /admin_log [lines] - Get the log of this bot.
    /admin_update - Do a manual update of the sustitution plan.
    """
    update.message.reply_text(text)


def admin_manual_update(update: Update, context: CallbackContext):
    if update.effective_user.username not in ADMINS: return
    add_admin_log(f"Manual update performed by @{update.effective_user.username}.")
    vplan = Vertretungsplan()
    vplan.update()
    vplan.save_to_file()
    update.message.reply_text("Pläne wurden aktualisiert!")


def admin_get_users(update: Update, context: CallbackContext):
    if update.effective_user.username not in ADMINS: return
    userdata = load_userdata()
    msg = ""
    for user in userdata:
        msg += f"@{user} - '{userdata[user][0]}'\n"
    update.message.reply_text(msg)


def admin_send_log(update: Update, context: CallbackContext):
    if update.effective_user.username not in ADMINS: return
    add_admin_log(f"Admin log sent to @{update.effective_user.username}.")
    with open("admin.log", "r") as f:
        admin_log = f.read().split("\n")

    if len(context.args) > 0:
        try:
            count = int(context.args[0])
        except ValueError:
            count = 10
    else:
        count = 10
    if count > len(admin_log):
        count = len(admin_log)

    message = "```\n" + "\n".join(admin_log[-count:]) + "\n```"
    update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)


def debug_check_name(update: Update, context: CallbackContext):
    if len(context.args) > 0:
        valid = Stundenplan.check_name(context.args[0])[0]
        if not valid:
            update.message.reply_text("Invalid Name")
        elif valid == [context.args[0]]:
            update.message.reply_text("Valid Name")
        else:
            update.message.reply_text("\n".join(valid))


def check_for_updates(context: CallbackContext):
    # update substitution plan
    vplan_old = Vertretungsplan()
    vplan_new = Vertretungsplan()
    vplan_new.update()
    vplan_new.save_to_file()

    # update time table
    userdata = load_userdata()
    for user in userdata:  # check for every user
        if userdata[user][0] != "":  # if user has a name
            splan = Stundenplan(userdata[user][0])
            splan.update()
            splan.save_to_file()
            # check substitution plan
            vplan_old_filtered = vplan_old.get_filtered(splan)
            vplan_new_filtered = vplan_new.get_filtered(splan)
            if vplan_old_filtered != vplan_new_filtered:  # substitution plan changed
                add_admin_log(f"Plan changed for user='@{user}', name='{userdata[user][0]}' -> Sending plan.")
                context.bot.send_message(userdata[user][1], "Dein Vertretungsplan hat sich geändert.")
                send_plan(user, context.bot.get_chat(userdata[user][1]), new_plan=True)


def main():
    with open('token', 'r') as f:
        token = f.read()

    updater = Updater(token, use_context=True)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('name', change_name))
    dispatcher.add_handler(CommandHandler('plan', plan))
    dispatcher.add_handler(CommandHandler('author', author))
    dispatcher.add_handler(CommandHandler('admin_help', admin_help))
    dispatcher.add_handler(CommandHandler('admin_update', admin_manual_update))
    dispatcher.add_handler(CommandHandler('admin_get_users', admin_get_users))
    dispatcher.add_handler(CommandHandler('admin_log', admin_send_log))
    dispatcher.add_handler(CommandHandler('debug_check_name', debug_check_name))
    dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), message_update))
    dispatcher.add_handler(CallbackQueryHandler(button))

    update_job = job_queue.run_repeating(check_for_updates, 5*60)

    updater.start_polling()
    add_admin_log("Bot has been started.")
    updater.idle()


if __name__ == "__main__":
    # chdir("/home/pi/VertretungsplanBot/")
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    add_admin_log("Starting bot...")
    main()
