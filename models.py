# MODELS

from pydantic.v1 import BaseModel

class BookingData(BaseModel):
    passenger_name:   str
    passenger_cnic:   str
    passenger_phone:  str
    passenger_type:   str
    train_id:         int
    travel_date:      str
    selected_class:   str
    seat_label:       str
    card_digits:      str
    user_source:      str = ""
    user_destination: str = ""
    email_id:         str = ""
    full_name:        str = ""