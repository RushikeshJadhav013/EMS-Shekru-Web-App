import uuid
import datetime
from firebase_admin import firestore
from typing import List, Optional
from app.core.config import settings

# Assume Firebase app is initialized at project startup.
from firebase_admin import credentials, initialize_app
import firebase_admin

if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    initialize_app(cred)

db = firestore.client()

# Utility functions for chat

def conversation_id(user1: int, user2: int) -> str:
    return "_".join(sorted([str(user1), str(user2)]))

def get_group_ref(group_id: str):
    return db.collection("groups").document(group_id)

def get_private_chat_ref(conv_id: str):
    return db.collection("private_chats").document(conv_id)

def get_message_collection(is_group: bool, chat_id: str):
    if is_group:
        return db.collection("groups").document(chat_id).collection("messages")
    else:
        return db.collection("private_chats").document(chat_id).collection("messages")

