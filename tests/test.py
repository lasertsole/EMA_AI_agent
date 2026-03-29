from context_engine import *

db=get_db()
def save_messages()->None:
    save_message(db, session_id="1", turn=1, role="human", content="123")

def get_messages1()->None:
    for item in get_messages(db=db, session_id="1"):
        print(item)

if __name__ == "__main__":
    # save_messages()
    get_messages1()