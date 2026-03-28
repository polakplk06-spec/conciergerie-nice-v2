import telebot
import requests
import json
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_ID = -1001746364485
TON_ID = 1281231556
CLAUDE_API_KEY = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
CLAUDE_BASE_URL = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL", "https://api.anthropic.com")

bot = telebot.TeleBot(TOKEN)

# Stockage temporaire pour pronos et sondages en attente
pending = {}

# Historique de conversation avec l'IA (liste de messages)
conversation_history = []

SYSTEM_PROMPT = """Tu es un assistant intelligent et polyvalent. Tu peux aider sur n'importe quel sujet : 
réfléchir à des concepts, brainstormer des idées, analyser des situations, rédiger du contenu, 
répondre à des questions générales, etc.
Tu as aussi une expertise en paris sportifs et pronostics football si le sujet vient sur le tapis.
Réponds de manière concise et claire, adapte ton ton à la question posée."""


def generer_message_ia(pronos):
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    prompt = f"""Tu es un pronostiqueur de paris sportifs professionnel et passioné. 
Génère un message Telegram accrocheur et dynamique pour ces pronos : {pronos}

Le message doit :
- Commencer par des emojis feu et un titre accrocheur
- Présenter chaque match avec l'heure si donnée
- Expliquer brièvement pourquoi ce prono en 1 phrase
- Finir par :
📲 Partage le canal : https://t.me/ykpronos77
💬 Questions en privé : @hazz0071

Utilise des emojis, sois dynamique et vendeur. Maximum 15 lignes."""

    data = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(f"{CLAUDE_BASE_URL}/v1/messages", headers=headers, json=data)
    result = response.json()
    if "content" not in result:
        raise Exception(f"Réponse API : {result}")
    return result["content"][0]["text"]


def generer_sondage_ia(sujet):
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    prompt = f"""Génère un sondage foot/sport pour Telegram sur ce sujet : {sujet}
    
Réponds UNIQUEMENT en JSON comme ceci :
{{"question": "la question du sondage", "options": ["option1", "option2", "option3", "option4"]}}

Maximum 4 options, question courte et fun."""

    data = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(f"{CLAUDE_BASE_URL}/v1/messages", headers=headers, json=data)
    result = response.json()
    texte = result["content"][0]["text"]
    texte = texte.replace("```json", "").replace("```", "").strip()
    return json.loads(texte)


def boutons_prono(msg_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Poster", callback_data=f"poster_{msg_id}"),
        InlineKeyboardButton("🔄 Régénérer", callback_data=f"regen_{msg_id}")
    )
    markup.row(InlineKeyboardButton("❌ Annuler", callback_data=f"annuler_{msg_id}"))
    return markup


def boutons_sondage(msg_id):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Poster", callback_data=f"spost_{msg_id}"),
        InlineKeyboardButton("🔄 Régénérer", callback_data=f"sregen_{msg_id}")
    )
    markup.row(InlineKeyboardButton("❌ Annuler", callback_data=f"sannul_{msg_id}"))
    return markup


def texte_preview_sondage(data):
    options_txt = "\n".join([f"  {i+1}. {o}" for i, o in enumerate(data["options"])])
    return f"📊 *Prévisualisation du sondage :*\n\n❓ {data['question']}\n\n{options_txt}"


# ─── COMMANDE /poster ──────────────────────────────────────────────

@bot.message_handler(commands=["poster"])
def cmd_poster(message):
    if message.chat.id != TON_ID:
        return
    pronos = message.text.replace("/poster", "").strip()
    if not pronos:
        bot.send_message(TON_ID, "Exemple : /poster PSG vs Lyon 21h00 PSG gagne")
        return
    try:
        msg_attente = bot.send_message(TON_ID, "⏳ Je génère le message...")
        message_genere = generer_message_ia(pronos)
        bot.delete_message(TON_ID, msg_attente.message_id)

        preview = bot.send_message(TON_ID, f"👁️ *Prévisualisation :*\n\n{message_genere}", parse_mode="Markdown")
        pending[preview.message_id] = {"type": "prono", "sujet": pronos, "message": message_genere}

        bot.send_message(TON_ID, "Que veux-tu faire ?", reply_markup=boutons_prono(preview.message_id))
    except Exception as e:
        bot.send_message(TON_ID, f"Erreur : {e}")


# ─── COMMANDE /sondage ────────────────────────────────────────────

@bot.message_handler(commands=["sondage"])
def cmd_sondage(message):
    if message.chat.id != TON_ID:
        return
    sujet = message.text.replace("/sondage", "").strip()
    if not sujet:
        bot.send_message(TON_ID, "Donne un thème ! Exemple : /sondage meilleur buteur de l'Euro")
        return
    try:
        msg_attente = bot.send_message(TON_ID, "⏳ Je génère le sondage...")
        sondage_data = generer_sondage_ia(sujet)
        bot.delete_message(TON_ID, msg_attente.message_id)

        preview = bot.send_message(TON_ID, texte_preview_sondage(sondage_data), parse_mode="Markdown")
        pending[preview.message_id] = {"type": "sondage", "sujet": sujet, "data": sondage_data}

        bot.send_message(TON_ID, "Que veux-tu faire ?", reply_markup=boutons_sondage(preview.message_id))
    except Exception as e:
        bot.send_message(TON_ID, f"Erreur : {e}")


# ─── GESTION DES BOUTONS ─────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.message.chat.id != TON_ID:
        return
    try:
        _handle_callback_inner(call)
    except Exception as e:
        try:
            bot.answer_callback_query(call.id, "❌ Erreur inattendue")
            bot.send_message(TON_ID, f"❌ Erreur : {e}")
        except:
            pass

def _handle_callback_inner(call):
    raw = call.data
    for prefix in ("spost_", "sregen_", "sannul_", "poster_", "regen_", "annuler_"):
        if raw.startswith(prefix):
            action = prefix.rstrip("_")
            msg_id = int(raw[len(prefix):])
            break
    else:
        return

    if action == "poster":
        if msg_id not in pending:
            bot.answer_callback_query(call.id, "❌ Session expirée, relance /poster")
            return
        try:
            bot.send_message(GROUP_ID, pending[msg_id]["message"])
            del pending[msg_id]
            bot.answer_callback_query(call.id, "✅ Posté !")
            bot.edit_message_text("✅ Prono posté dans le canal !", TON_ID, call.message.message_id)
        except Exception as e:
            bot.answer_callback_query(call.id, "Erreur")
            bot.edit_message_text(f"Erreur : {e}", TON_ID, call.message.message_id)

    elif action == "regen":
        if msg_id not in pending:
            bot.answer_callback_query(call.id, "❌ Session expirée, relance /poster")
            return
        pronos = pending[msg_id]["sujet"]
        bot.answer_callback_query(call.id, "🔄 Régénération...")
        try:
            bot.edit_message_text("⏳ Je régénère...", TON_ID, call.message.message_id)
            nouveau = generer_message_ia(pronos)
            pending[msg_id]["message"] = nouveau
            bot.edit_message_text(f"👁️ *Prévisualisation :*\n\n{nouveau}", TON_ID, msg_id, parse_mode="Markdown")
            bot.edit_message_text("Que veux-tu faire ?", TON_ID, call.message.message_id, reply_markup=boutons_prono(msg_id))
        except Exception as e:
            bot.edit_message_text(f"Erreur : {e}", TON_ID, call.message.message_id)

    elif action == "annuler":
        if msg_id in pending:
            del pending[msg_id]
        bot.answer_callback_query(call.id, "❌ Annulé")
        bot.edit_message_text("❌ Annulé.", TON_ID, call.message.message_id)

    elif action == "spost":
        if msg_id not in pending:
            bot.answer_callback_query(call.id, "❌ Session expirée, relance /sondage")
            return
        try:
            d = pending[msg_id]["data"]
            bot.send_poll(GROUP_ID, d["question"], d["options"], is_anonymous=True)
            del pending[msg_id]
            bot.answer_callback_query(call.id, "✅ Sondage posté !")
            bot.edit_message_text("✅ Sondage posté dans le canal !", TON_ID, call.message.message_id)
        except Exception as e:
            bot.answer_callback_query(call.id, "Erreur")
            bot.edit_message_text(f"Erreur : {e}", TON_ID, call.message.message_id)

    elif action == "sregen":
        if msg_id not in pending:
            bot.answer_callback_query(call.id, "❌ Session expirée, relance /sondage")
            return
        sujet = pending[msg_id]["sujet"]
        bot.answer_callback_query(call.id, "🔄 Régénération...")
        try:
            bot.edit_message_text("⏳ Je régère...", TON_ID, call.message.message_id)
            nouveau = generer_sondage_ia(sujet)
            pending[msg_id]["data"] = nouveau
            bot.edit_message_text(texte_preview_sondage(nouveau), TON_ID, msg_id, parse_mode="Markdown")
            bot.edit_message_text("Que veux-tu faire ?", TON_ID, call.message.message_id, reply_markup=boutons_sondage(msg_id))
        except Exception as e:
            bot.edit_message_text(f"Erreur : {e}", TON_ID, call.message.message_id)

    elif action == "sannul":
        if msg_id in pending:
            del pending[msg_id]
        bot.answer_callback_query(call.id, "❌ Annulé")
        bot.edit_message_text("❌ Annulé.", TON_ID, call.message.message_id)


# ─── COMMANDE /aide ──────────────────────────────────────────────

@bot.message_handler(commands=["aide", "help"])
def cmd_aide(message):
    if message.chat.id != TON_ID:
        return
    bot.send_message(
        TON_ID,
        "📋 *Commandes disponibles :*\n\n"
        "🎯 *Pronos & Canal*\n"
        "/poster <pronos> — Génère et poste un prono\n"
        "/sondage <thème> — Génère un sondage\n\n"
        "🤖 *Chat avec l'IA*\n"
        "Envoie n'importe quel message pour discuter avec l'IA !\n"
        "/clear — Efface l'historique de conversation\n\n"
        "💬 *Exemples :*\n"
        "`/poster PSG vs Lyon 21h00 PSG gagne`\n"
        "`/sondage meilleur buteur de l'Euro`\n"
        "`Aide-moi à rédiger une bio pour mon canal`",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["clear"])
def cmd_clear(message):
    if message.chat.id != TON_ID:
        return
    global conversation_history
    conversation_history = []
    bot.send_message(TON_ID, "🗑️ Historique effacé. Nouvelle conversation !")


# ─── CHAT AVEC L'IA ──────────────────────────────────────────────

@bot.message_handler(func=lambda message: True)
def chat_ia(message):
    if message.chat.id != TON_ID:
        return

    texte = message.text.strip()
    if not texte:
        return

    conversation_history.append({"role": "user", "content": texte})

    if len(conversation_history) > 20:
        conversation_history.pop(0)
        if conversation_history and conversation_history[0]["role"] == "assistant":
            conversation_history.pop(0)

    try:
        msg_attente = bot.send_message(TON_ID, "💭 ...")

        headers = {
            "x-api-key": CLAUDE_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        data = {
            "model": "claude-sonnet-4-6",
            "max_tokens": 1500,
            "system": SYSTEM_PROMPT,
            "messages": conversation_history
        }
        response = requests.post(f"{CLAUDE_BASE_URL}/v1/messages", headers=headers, json=data)
        result = response.json()

        if "content" not in result:
            raise Exception(f"Réponse API : {result}")

        reponse_ia = result["content"][0]["text"]
        conversation_history.append({"role": "assistant", "content": reponse_ia})

        bot.delete_message(TON_ID, msg_attente.message_id)
        bot.send_message(TON_ID, reponse_ia)

    except Exception as e:
        if conversation_history and conversation_history[-1]["role"] == "user":
            conversation_history.pop()
        try:
            bot.delete_message(TON_ID, msg_attente.message_id)
        except:
            pass
        bot.send_message(TON_ID, f"❌ Erreur : {e}")


print("🤖 Bot démarré...")
bot.infinity_polling(timeout=30, long_polling_timeout=30, logger_level=None, allowed_updates=None, restart_on_change=False, none_stop=True)
