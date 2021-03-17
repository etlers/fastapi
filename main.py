from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

import os

app = FastAPI()


class Item(BaseModel):
    name: str
    price: float
    is_offer: Optional[bool] = None

dic_opt_code = {
    10001: "basic_query",
    10002: "buy"
}


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None, n: Optional[str] = None):
    return {"item_id": item_id, "q": q, "n":n}


@app.get("/trading/items/{opt_code}")
def trading_stock(opt_code: int, q: Optional[str] = None, n: Optional[str] = None):
    os.system("python3 called.py")
    return {"opt_code": opt_code, "q": q, "n":n}


@app.put("/items/{item_id}")
def update_item(item_id: int, item: Item):
    return {"item_name": item.name, "item_id": item_id}
