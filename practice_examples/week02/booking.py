"""booking.py — Week 2 practice: author a Pydantic model and feel validation.
    python practice_examples/week02/booking.py
"""
from typing import Optional
from pydantic import BaseModel


class Booking(BaseModel):
    guest: str
    nights: int
    email: Optional[str] = None


print(Booking(guest="Sam", nights="3"))        # coercion: "3" -> 3
print(Booking(guest="Sam", nights="three"))    # raises ValidationError
