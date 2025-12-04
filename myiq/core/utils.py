import uuid

def get_req_id() -> str:
    return str(uuid.uuid4().int)[:10]

def get_sub_id() -> str:
    return f"s_{uuid.uuid4().hex[:4]}"
